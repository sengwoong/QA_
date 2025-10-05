"""
sabangnet_API RAG 시스템
Faiss를 이용한 벡터 검색 기반 질문-답변 시스템
"""

import os
import json
import sqlite3
import pickle
import hashlib
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import asyncio
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# OpenAI 라이브러리
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("OpenAI 라이브러리가 설치되지 않았습니다. pip install openai")

# 벡터 검색 비활성화 - GPT 기반 검색 사용
    VECTOR_AVAILABLE = False

@dataclass
class Document:
    """문서 구조체"""
    id: str
    title: str
    content: str
    category: str
    tags: List[str]
    file_path: str
    line_start: int
    line_end: int
    created_at: datetime
    metadata: Dict[str, Any]

@dataclass
class QueryResult:
    """검색 결과 구조체"""
    document: Document
    score: float
    matched_sections: List[str]

class SabangnetRAGSystem:
    """사방넷 RAG 시스템 - Faiss 기반 + GPT"""
    
    def __init__(self, sabangnet_path: str = "../../../sabangnet_API", db_path: str = "sabangnet_rag.db"):
        self.sabangnet_path = Path(sabangnet_path)
        self.db_path = db_path
        self.documents: List[Document] = []
        
        # OpenAI 클라이언트 초기화
        self.openai_client = None
        if OPENAI_AVAILABLE:
            api_key = os.getenv("GPTKEY")
            if api_key:
                self.openai_client = OpenAI(api_key=api_key)
                print("GPT API 클라이언트 초기화 완료")
            else:
                print("GPTKEY 환경변수가 설정되지 않았습니다.")
        
        print("GPT 기반 검색 모드로 설정되었습니다.")
        
        self._init_database()
        self._load_documents()
    
    def _init_database(self):
        """데이터베이스 초기화"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 문서 테이블 생성
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT NOT NULL,
                tags TEXT,
                file_path TEXT,
                line_start INTEGER,
                line_end INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        ''')
        
        # 벡터 임베딩 테이블 제거 - GPT 기반 검색 사용
        
        conn.commit()
        conn.close()
    
    def _load_documents(self):
        """저장된 문서들을 메모리로 로드"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM documents')
        rows = cursor.fetchall()
        
        for row in rows:
            doc = Document(
                id=row[0],
                title=row[1],
                content=row[2],
                category=row[3],
                tags=json.loads(row[4]) if row[4] else [],
                file_path=row[5],
                line_start=row[6],
                line_end=row[7],
                created_at=datetime.fromisoformat(row[8]),
                metadata=json.loads(row[9]) if row[9] else {}
            )
            self.documents.append(doc)
        
        conn.close()
        print(f"로드된 문서 수: {len(self.documents)}")
    
    # Faiss 인덱스 구축 제거 - GPT 기반 검색 사용
    
    def extract_sabangnet_documents(self):
        """sabangnet_API에서 모든 문서 추출"""
        if not self.sabangnet_path.exists():
            print(f"sabangnet_API 경로가 존재하지 않습니다: {self.sabangnet_path}")
            return
        
        print("sabangnet_API 문서 추출 시작...")
        
        # 추출할 파일 확장자
        target_extensions = {'.py', '.md', '.txt', '.yml', '.yaml', '.json', '.ini'}
        
        # 제외할 디렉토리
        exclude_dirs = {'__pycache__', '.git', 'node_modules', '.pytest_cache', 'venv', 'env'}
        
        total_files = 0
        for root, dirs, files in os.walk(self.sabangnet_path):
            # 제외 디렉토리 필터링
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for file in files:
                if Path(file).suffix in target_extensions:
                    file_path = Path(root) / file
                    self._extract_file_content(file_path)
                    total_files += 1
        
        print(f"총 {total_files}개 파일에서 문서 추출 완료")
        print(f"총 {len(self.documents)}개 문서 생성")
    
    def _extract_file_content(self, file_path: Path):
        """개별 파일에서 내용 추출 - 의미있는 단위로 분할"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            if not content.strip():
                return
            
            # 파일 타입에 따른 카테고리 분류
            category = self._get_file_category(file_path)
            
            # 파일 내용 분석
            content_analysis = self._analyze_file_content(content, file_path)
            
            # 파일 타입별로 다른 파싱 전략 적용
            if file_path.suffix == '.py':
                # Python 파일: 함수, 클래스, API 엔드포인트 단위로 분할
                chunks = self._parse_python_file(content, file_path)
            elif file_path.suffix in ['.md', '.txt']:
                # 문서 파일: 섹션 단위로 분할
                chunks = self._parse_document_file(content, file_path)
            elif file_path.suffix in ['.yml', '.yaml', '.json']:
                # 설정 파일: 전체를 하나의 청크로
                chunks = [{'type': 'config', 'content': content, 'title': f"설정: {file_path.name}"}]
            else:
                # 기타 파일: 기본 청크 분할
                chunks = self._split_content_into_chunks(content, file_path)
            
            for i, chunk_data in enumerate(chunks):
                if isinstance(chunk_data, dict):
                    # 구조화된 청크 데이터
                    doc_id = hashlib.md5(f"{file_path}_{chunk_data.get('type', 'chunk')}_{i}_{datetime.now()}".encode()).hexdigest()
                    
                    # 컨텍스트 기반 임베딩용 텍스트 생성
                    embedding_text = self._create_contextual_embedding_text(
                        chunk_data.get('content', ''),
                        file_path,
                        category,
                        chunk_data,
                        content_analysis
                    )
                    
                    doc = Document(
                        id=doc_id,
                        title=chunk_data.get('title', f"{file_path.name} (청크 {i+1})"),
                        content=embedding_text,  # 임베딩용 텍스트 사용
                        category=category,
                        tags=chunk_data.get('tags', []) + self._extract_tags(chunk_data.get('content', ''), file_path),
                        file_path=str(file_path),
                        line_start=chunk_data.get('line_start', 0),
                        line_end=chunk_data.get('line_end', 0),
                        created_at=datetime.now(),
                        metadata={
                            "file_type": file_path.suffix,
                            "file_size": len(content),
                            "chunk_index": i,
                            "total_chunks": len(chunks),
                            "chunk_type": chunk_data.get('type', 'general'),
                            "function_name": chunk_data.get('function_name', ''),
                            "class_name": chunk_data.get('class_name', ''),
                            "api_endpoint": chunk_data.get('api_endpoint', ''),
                            "table_name": chunk_data.get('table_name', ''),
                            "business_domain": content_analysis.get('business_domain', ''),
                            "technical_components": content_analysis.get('technical_components', []),
                            "data_entities": content_analysis.get('data_entities', []),
                            "original_content": chunk_data.get('content', '')  # 원본 내용 보존
                        }
                    )
                else:
                    # 일반 텍스트 청크
                    doc_id = hashlib.md5(f"{file_path}_{i}_{datetime.now()}".encode()).hexdigest()
                    
                    embedding_text = self._create_contextual_embedding_text(
                        chunk_data,
                        file_path,
                        category,
                        {'type': 'general', 'content': chunk_data},
                        content_analysis
                    )
                    
                    doc = Document(
                        id=doc_id,
                        title=f"{file_path.name} (청크 {i+1})",
                        content=embedding_text,
                        category=category,
                        tags=self._extract_tags(chunk_data, file_path),
                        file_path=str(file_path),
                        line_start=0,
                        line_end=0,
                        created_at=datetime.now(),
                        metadata={
                            "file_type": file_path.suffix,
                            "file_size": len(content),
                            "chunk_index": i,
                            "total_chunks": len(chunks),
                            "business_domain": content_analysis.get('business_domain', ''),
                            "original_content": chunk_data
                        }
                    )
                
                self._save_document(doc)
                
        except Exception as e:
            print(f"파일 추출 실패 {file_path}: {e}")
    
    def _get_file_category(self, file_path: Path) -> str:
        """파일 경로를 기반으로 카테고리 결정"""
        path_str = str(file_path)
        
        if 'models/' in path_str:
            return 'database_model'
        elif 'controller/' in path_str:
            return 'controller'
        elif 'services/' in path_str:
            return 'service'
        elif 'api/' in path_str:
            return 'api_endpoint'
        elif 'schemas/' in path_str:
            return 'schema'
        elif 'repository/' in path_str:
            return 'repository'
        elif 'utils/' in path_str:
            return 'utility'
        elif 'tests/' in path_str:
            return 'test'
        elif file_path.name in ['README.md', 'requirements.txt', 'app.py', 'main.py']:
            return 'main'
        else:
            return 'other'
    
    def _split_content_into_chunks(self, content: str, file_path: Path) -> List[str]:
        """내용을 청크로 분할"""
        max_chunk_size = 2000  # 최대 청크 크기
        
        if len(content) <= max_chunk_size:
            return [content]
        
        chunks = []
        lines = content.split('\n')
        current_chunk = []
        current_size = 0
        
        for line in lines:
            line_size = len(line) + 1  # +1 for newline
            
            if current_size + line_size > max_chunk_size and current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = [line]
                current_size = line_size
            else:
                current_chunk.append(line)
                current_size += line_size
        
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
        
        return chunks
    
    def _analyze_file_content(self, content: str, file_path: Path) -> Dict:
        """파일 내용을 분석하여 의미있는 메타데이터 추출"""
        analysis = {
            'primary_category': 'unknown',
            'secondary_categories': [],
            'business_domain': 'unknown',
            'technical_components': [],
            'data_entities': [],
            'api_endpoints': [],
            'dependencies': []
        }
        
        # 1. 비즈니스 도메인 분석
        if any(keyword in content.lower() for keyword in ['order', '주문', 'order_list']):
            analysis['business_domain'] = 'order_management'
            analysis['secondary_categories'].append('주문관리')
        
        if any(keyword in content.lower() for keyword in ['product', '상품', 'product_create']):
            analysis['business_domain'] = 'product_management'
            analysis['secondary_categories'].append('상품관리')
        
        if any(keyword in content.lower() for keyword in ['batch', '배치', 'macro']):
            analysis['business_domain'] = 'batch_processing'
            analysis['secondary_categories'].append('배치처리')
        
        if any(keyword in content.lower() for keyword in ['shipment', '배송', 'hanjin']):
            analysis['business_domain'] = 'shipping_management'
            analysis['secondary_categories'].append('배송관리')
        
        # 2. 기술적 컴포넌트 분석
        if 'class ' in content and 'Base' in content:
            analysis['technical_components'].append('database_model')
        
        if '@router.' in content or 'APIRouter' in content:
            analysis['technical_components'].append('api_endpoint')
        
        if 'async def' in content and 'service' in str(file_path):
            analysis['technical_components'].append('service_layer')
        
        if 'controller' in str(file_path).lower():
            analysis['technical_components'].append('controller')
        
        # 3. 데이터 엔티티 추출
        table_names = re.findall(r'__tablename__ = ["\']([^"\']+)["\']', content)
        analysis['data_entities'].extend(table_names)
        
        # 4. API 엔드포인트 추출
        endpoints = re.findall(r'@router\.(get|post|put|delete)\(["\']([^"\']+)["\']', content)
        analysis['api_endpoints'].extend([f"{method.upper()} {path}" for method, path in endpoints])
        
        return analysis
    
    def _parse_python_file(self, content: str, file_path: Path) -> List[Dict]:
        """Python 파일을 의미있는 단위로 분할"""
        chunks = []
        lines = content.split('\n')
        
        # 1. 클래스 추출
        class_pattern = r'^class\s+(\w+).*?:'
        for i, line in enumerate(lines):
            match = re.match(class_pattern, line.strip())
            if match:
                class_name = match.group(1)
                class_content, end_line = self._extract_class_content(lines, i)
                
                chunks.append({
                    'type': 'class',
                    'title': f"클래스: {class_name}",
                    'content': class_content,
                    'class_name': class_name,
                    'line_start': i + 1,
                    'line_end': end_line,
                    'tags': ['클래스', class_name]
                })
        
        # 2. 함수 추출
        function_pattern = r'^(async\s+)?def\s+(\w+).*?:'
        for i, line in enumerate(lines):
            match = re.match(function_pattern, line.strip())
            if match:
                function_name = match.group(2)
                func_content, end_line = self._extract_function_content(lines, i)
                
                chunks.append({
                    'type': 'function',
                    'title': f"함수: {function_name}",
                    'content': func_content,
                    'function_name': function_name,
                    'line_start': i + 1,
                    'line_end': end_line,
                    'tags': ['함수', function_name]
                })
        
        # 3. API 엔드포인트 추출
        api_pattern = r'@router\.(get|post|put|delete)\(["\']([^"\']+)["\']'
        for i, line in enumerate(lines):
            match = re.search(api_pattern, line)
            if match:
                method = match.group(1).upper()
                path = match.group(2)
                
                # 다음 함수까지의 내용 추출
                func_content, end_line = self._extract_function_content(lines, i + 1)
                
                chunks.append({
                    'type': 'api_endpoint',
                    'title': f"API: {method} {path}",
                    'content': func_content,
                    'api_endpoint': f"{method} {path}",
                    'line_start': i + 1,
                    'line_end': end_line,
                    'tags': ['API', method, path]
                })
        
        # 4. 테이블 모델 추출
        table_pattern = r'__tablename__ = ["\']([^"\']+)["\']'
        for i, line in enumerate(lines):
            match = re.search(table_pattern, line)
            if match:
                table_name = match.group(1)
                
                # 클래스 전체 내용 추출
                class_start = self._find_class_start(lines, i)
                if class_start >= 0:
                    class_content, end_line = self._extract_class_content(lines, class_start)
                    
                    chunks.append({
                        'type': 'database_model',
                        'title': f"테이블: {table_name}",
                        'content': class_content,
                        'table_name': table_name,
                        'line_start': class_start + 1,
                        'line_end': end_line,
                        'tags': ['테이블', table_name]
                    })
        
        return chunks if chunks else [{'type': 'general', 'content': content, 'title': f"파일: {file_path.name}"}]
    
    def _parse_document_file(self, content: str, file_path: Path) -> List[Dict]:
        """문서 파일을 섹션 단위로 분할"""
        chunks = []
        sections = content.split('\n\n')
        
        for i, section in enumerate(sections):
            if section.strip():
                # 섹션 제목 추출
                lines = section.strip().split('\n')
                title = lines[0] if lines else f"섹션 {i+1}"
                
                chunks.append({
                    'type': 'document_section',
                    'title': title,
                    'content': section.strip(),
                    'tags': ['문서', '섹션']
                })
        
        return chunks if chunks else [{'type': 'document', 'content': content, 'title': f"문서: {file_path.name}"}]
    
    def _extract_class_content(self, lines: List[str], start_line: int) -> Tuple[str, int]:
        """클래스 내용 추출"""
        content_lines = []
        indent_level = len(lines[start_line]) - len(lines[start_line].lstrip())
        current_line = start_line
        
        # 클래스 시작 라인 추가
        content_lines.append(lines[start_line])
        current_line += 1
        
        # 클래스 내용 추출
        while current_line < len(lines):
            line = lines[current_line]
            
            # 빈 라인은 추가
            if not line.strip():
                content_lines.append(line)
                current_line += 1
                continue
            
            # 현재 들여쓰기 레벨 확인
            current_indent = len(line) - len(line.lstrip())
            
            # 같은 레벨의 클래스나 함수가 시작되면 중단
            if current_indent <= indent_level and (line.strip().startswith('class ') or line.strip().startswith('def ')):
                break
            
            content_lines.append(line)
            current_line += 1
        
        return '\n'.join(content_lines), current_line - 1
    
    def _extract_function_content(self, lines: List[str], start_line: int) -> Tuple[str, int]:
        """함수 내용 추출"""
        content_lines = []
        indent_level = len(lines[start_line]) - len(lines[start_line].lstrip())
        current_line = start_line
        
        # 함수 시작 라인 추가
        content_lines.append(lines[start_line])
        current_line += 1
        
        # 함수 내용 추출
        while current_line < len(lines):
            line = lines[current_line]
            
            # 빈 라인은 추가
            if not line.strip():
                content_lines.append(line)
                current_line += 1
                continue
            
            # 현재 들여쓰기 레벨 확인
            current_indent = len(line) - len(line.lstrip())
            
            # 같은 레벨의 함수나 클래스가 시작되면 중단
            if current_indent <= indent_level and (line.strip().startswith('def ') or line.strip().startswith('class ')):
                break
            
            content_lines.append(line)
            current_line += 1
        
        return '\n'.join(content_lines), current_line - 1
    
    def _find_class_start(self, lines: List[str], line_index: int) -> int:
        """테이블 정의가 포함된 클래스의 시작 위치 찾기"""
        for i in range(line_index, -1, -1):
            if lines[i].strip().startswith('class '):
                return i
        return -1
    
    def _create_contextual_embedding_text(self, content: str, file_path: Path, category: str, chunk_data: Dict, content_analysis: Dict) -> str:
        """문서의 컨텍스트를 고려한 임베딩용 텍스트 생성"""
        context_parts = []
        
        # 1. 기본 정보
        context_parts.append(f"파일: {file_path.name}")
        context_parts.append(f"경로: {file_path}")
        context_parts.append(f"카테고리: {category}")
        
        # 2. 청크 타입 정보
        chunk_type = chunk_data.get('type', 'general')
        context_parts.append(f"타입: {chunk_type}")
        
        # 3. 메타데이터 정보
        if chunk_data.get('class_name'):
            context_parts.append(f"클래스: {chunk_data['class_name']}")
        
        if chunk_data.get('function_name'):
            context_parts.append(f"함수: {chunk_data['function_name']}")
        
        if chunk_data.get('api_endpoint'):
            context_parts.append(f"API: {chunk_data['api_endpoint']}")
        
        if chunk_data.get('table_name'):
            context_parts.append(f"테이블: {chunk_data['table_name']}")
        
        # 4. 비즈니스 도메인 정보
        if content_analysis.get('business_domain'):
            context_parts.append(f"도메인: {content_analysis['business_domain']}")
        
        # 5. 기술적 컴포넌트
        if content_analysis.get('technical_components'):
            context_parts.append(f"기술컴포넌트: {', '.join(content_analysis['technical_components'])}")
        
        # 6. 데이터 엔티티
        if content_analysis.get('data_entities'):
            context_parts.append(f"데이터엔티티: {', '.join(content_analysis['data_entities'])}")
        
        # 7. 실제 코드 내용
        context_parts.append(f"내용: {content}")
        
        # 8. 태그 정보
        if chunk_data.get('tags'):
            context_parts.append(f"태그: {', '.join(chunk_data['tags'])}")
        
        return "\n".join(context_parts)
    
    def _extract_tags(self, content: str, file_path: Path) -> List[str]:
        """내용에서 태그 추출"""
        tags = []
        
        # 파일명에서 태그 추출
        file_name = file_path.stem.lower()
        if 'order' in file_name:
            tags.append('주문')
        if 'product' in file_name:
            tags.append('상품')
        if 'user' in file_name:
            tags.append('사용자')
        if 'auth' in file_name:
            tags.append('인증')
        if 'api' in file_name:
            tags.append('API')
        if 'test' in file_name:
            tags.append('테스트')
        
        # 내용에서 키워드 추출
        keywords = ['smile', 'hanjin', 'ecount', 'gmarket', 'batch', 'macro', 'erp']
        for keyword in keywords:
            if keyword.lower() in content.lower():
                tags.append(keyword)
        
        return list(set(tags))  # 중복 제거
    
    def _save_document(self, doc: Document):
        """문서를 데이터베이스에 저장"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO documents 
            (id, title, content, category, tags, file_path, line_start, line_end, created_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            doc.id, doc.title, doc.content, doc.category,
            json.dumps(doc.tags), doc.file_path, doc.line_start, doc.line_end,
            doc.created_at.isoformat(), json.dumps(doc.metadata)
        ))
        
        # 벡터 임베딩 생성 제거 - GPT 기반 검색 사용
        
        conn.commit()
        conn.close()
        
        self.documents.append(doc)
    
    def search(self, query: str, limit: int = 10, category: str = None) -> List[QueryResult]:
        """GPT 기반 문서 검색"""
        return self._gpt_based_search(query, limit, category)
    
    def _gpt_based_search(self, query: str, limit: int, category: str = None) -> List[QueryResult]:
        """GPT 기반 지능형 문서 검색 - 토큰 최적화"""
        if not self.openai_client:
            return self._fallback_search(query, limit, category)
        
        try:
            # 1단계: 키워드 기반 사전 필터링
            filtered_docs = self._pre_filter_documents(query, category, max_docs=50)
            
            if not filtered_docs:
                return self._fallback_search(query, limit, category)
            
            # 2단계: GPT를 통한 최종 문서 선택
            documents_info = []
            for i, doc in enumerate(filtered_docs):
                # 간단한 문서 정보만 생성
                summary = f"문서 {i+1}: {doc.title}\n"
                summary += f"파일: {doc.file_path}\n"
                
                # 메타데이터 정보 추가
                if doc.metadata.get('class_name'):
                    summary += f"클래스: {doc.metadata['class_name']}\n"
                if doc.metadata.get('function_name'):
                    summary += f"함수: {doc.metadata['function_name']}\n"
                if doc.metadata.get('api_endpoint'):
                    summary += f"API: {doc.metadata['api_endpoint']}\n"
                if doc.metadata.get('table_name'):
                    summary += f"테이블: {doc.metadata['table_name']}\n"
                
                # 내용 요약 (처음 100자)
                content_preview = doc.metadata.get('original_content', doc.content)[:100]
                summary += f"내용: {content_preview}...\n"
                summary += "---\n"
                
                documents_info.append((i, summary))
            
            # GPT에게 관련 문서 선택 요청
            prompt = f"""다음은 sabangnet_API 코드베이스의 문서들입니다.

사용자 질문: "{query}"

다음 문서들 중에서 질문에 가장 관련성이 높은 문서들의 번호를 선택해주세요. 
최대 {limit}개의 문서 번호를 쉼표로 구분하여 답변해주세요.

문서 목록:
{''.join([f"{i+1}. {info}" for i, info in enumerate(documents_info)])}

관련 문서 번호만 답변해주세요:"""

            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "당신은 코드베이스 분석 전문가입니다. 주어진 질문에 가장 관련성이 높은 문서들을 선택해주세요."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100,
                temperature=0.1
            )
            
            # GPT 응답에서 문서 번호 추출
            selected_text = response.choices[0].message.content.strip()
            selected_indices = []
            
            # 숫자 추출
            import re
            numbers = re.findall(r'\d+', selected_text)
            for num_str in numbers:
                try:
                    idx = int(num_str) - 1  # 1-based to 0-based
                    if 0 <= idx < len(filtered_docs):
                        selected_indices.append(idx)
                except ValueError:
                    continue
            
            # 선택된 문서들로 결과 생성
            results = []
            for idx in selected_indices[:limit]:
                if idx < len(filtered_docs):
                    doc = filtered_docs[idx]
                    results.append(QueryResult(
                        document=doc,
                        score=1.0 - (len(results) * 0.1),  # 순서에 따른 점수
                        matched_sections=[doc.metadata.get('original_content', doc.content)]
                    ))
            
            return results
            
        except Exception as e:
            print(f"GPT 검색 실패: {e}")
            return self._fallback_search(query, limit, category)
    
    def _pre_filter_documents(self, query: str, category: str = None, max_docs: int = 50) -> List[Document]:
        """키워드 기반 사전 필터링"""
        query_words = re.findall(r'\b\w+\b', query.lower())
        scored_docs = []
        
        for doc in self.documents:
            if category and doc.category != category:
                continue
            
            score = 0
            
            # 파일명 매칭 (높은 점수)
            file_name = doc.file_path.lower()
            for word in query_words:
                if word in file_name:
                    score += 3
            
            # 제목 매칭
            title = doc.title.lower()
            for word in query_words:
                if word in title:
                    score += 2
            
            # 메타데이터 매칭
            if doc.metadata.get('class_name'):
                class_name = doc.metadata['class_name'].lower()
                for word in query_words:
                    if word in class_name:
                        score += 2
            
            if doc.metadata.get('function_name'):
                func_name = doc.metadata['function_name'].lower()
                for word in query_words:
                    if word in func_name:
                        score += 2
            
            if doc.metadata.get('api_endpoint'):
                api_endpoint = doc.metadata['api_endpoint'].lower()
                for word in query_words:
                    if word in api_endpoint:
                        score += 2
            
            if doc.metadata.get('table_name'):
                table_name = doc.metadata['table_name'].lower()
                for word in query_words:
                    if word in table_name:
                        score += 2
            
            # 내용 매칭 (낮은 점수)
            content = doc.metadata.get('original_content', doc.content).lower()
            for word in query_words:
                if word in content:
                    score += 1
            
            if score > 0:
                scored_docs.append((score, doc))
        
        # 점수순 정렬 후 상위 문서 반환
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        return [doc for score, doc in scored_docs[:max_docs]]
    
    def _fallback_search(self, query: str, limit: int, category: str = None) -> List[QueryResult]:
        """키워드 기반 폴백 검색"""
        query_words = re.findall(r'\b\w+\b', query.lower())
        results = []
        
        for doc in self.documents:
            if category and doc.category != category:
                continue
            
            # 키워드 매칭 점수 계산
            content_lower = doc.content.lower()
            score = sum(1 for word in query_words if word in content_lower)
            score = score / len(query_words) if query_words else 0
            
            if score > 0:
                results.append(QueryResult(
                    document=doc,
                    score=score,
                    matched_sections=[doc.content[:300] + "..." if len(doc.content) > 300 else doc.content]
                ))
        
        # 점수순 정렬
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]
    
    def answer_question(self, question: str, context_limit: int = 5) -> str:
        """질문에 대한 답변 생성"""
        # 질문 분석
        question_analysis = self._analyze_question_type(question)
        
        # 전략적 검색
        results = self._strategic_search(question, question_analysis, context_limit)
        
        if not results:
            return "관련 정보를 찾을 수 없습니다."
        
        # 컨텍스트 구성
        context_parts = []
        for result in results:
            # 원본 내용 사용 (임베딩용 텍스트가 아닌)
            original_content = result.document.metadata.get('original_content', result.document.content)
            
            context_parts.append(f"파일: {result.document.file_path}")
            context_parts.append(f"카테고리: {result.document.category}")
            
            # 메타데이터 정보 추가
            if result.document.metadata.get('class_name'):
                context_parts.append(f"클래스: {result.document.metadata['class_name']}")
            if result.document.metadata.get('function_name'):
                context_parts.append(f"함수: {result.document.metadata['function_name']}")
            if result.document.metadata.get('api_endpoint'):
                context_parts.append(f"API: {result.document.metadata['api_endpoint']}")
            if result.document.metadata.get('table_name'):
                context_parts.append(f"테이블: {result.document.metadata['table_name']}")
            
            context_parts.append(f"내용: {original_content}")
            context_parts.append("---")
        
        context = "\n".join(context_parts)
        
        # GPT를 사용한 답변 생성
        if self.openai_client:
            try:
                # 질문 유형에 따른 시스템 프롬프트 조정
                system_prompt = self._get_system_prompt(question_analysis)
                
                response = self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {
                            "role": "system", 
                            "content": system_prompt
                        },
                        {
                            "role": "user",
                            "content": f"""질문: {question}

관련 코드베이스 정보:
{context}

위 정보를 바탕으로 질문에 대한 상세하고 정확한 답변을 작성해주세요."""
                        }
                    ],
                    max_tokens=1000,
                    temperature=0.3
                )
                
                return response.choices[0].message.content.strip()
                
            except Exception as e:
                print(f"GPT API 호출 실패: {e}")
                # GPT 실패 시 폴백 답변
                return self._generate_fallback_answer(question, context)
        else:
            # GPT가 없을 때 폴백 답변
            return self._generate_fallback_answer(question, context)
    
    def _analyze_question_type(self, question: str) -> Dict:
        """질문 유형을 분석하여 검색 전략 결정"""
        question_lower = question.lower()
        
        analysis = {
            'type': 'general',
            'entities': [],
            'intent': 'unknown',
            'search_strategy': 'semantic'
        }
        
        # 1. 질문 유형 분류
        if any(keyword in question_lower for keyword in ['어떻게', 'how', '방법', '작동']):
            analysis['type'] = 'how_to'
            analysis['intent'] = 'process_explanation'
        
        elif any(keyword in question_lower for keyword in ['어디에', 'where', '위치', '파일']):
            analysis['type'] = 'location'
            analysis['intent'] = 'file_location'
        
        elif any(keyword in question_lower for keyword in ['무엇', 'what', '구조', '설명']):
            analysis['type'] = 'what_is'
            analysis['intent'] = 'definition'
        
        # 2. 엔티티 추출
        entities = []
        if '테이블' in question_lower or 'table' in question_lower:
            entities.append('database_table')
        
        if 'api' in question_lower or '엔드포인트' in question_lower:
            entities.append('api_endpoint')
        
        if '컨트롤러' in question_lower or 'controller' in question_lower:
            entities.append('controller')
        
        if '서비스' in question_lower or 'service' in question_lower:
            entities.append('service')
        
        if '모델' in question_lower or 'model' in question_lower:
            entities.append('database_model')
        
        analysis['entities'] = entities
        
        # 3. 검색 전략 결정
        if analysis['type'] == 'location':
            analysis['search_strategy'] = 'metadata_based'
        elif analysis['type'] == 'how_to':
            analysis['search_strategy'] = 'process_based'
        else:
            analysis['search_strategy'] = 'semantic'
        
        return analysis
    
    def _strategic_search(self, question: str, question_analysis: Dict, limit: int) -> List[QueryResult]:
        """질문 분석 결과를 바탕으로 전략적 검색"""
        strategy = question_analysis['search_strategy']
        entities = question_analysis['entities']
        
        if strategy == 'metadata_based':
            # 메타데이터 기반 검색 (위치 찾기)
            return self._metadata_based_search(question, entities, limit)
        elif strategy == 'process_based':
            # 프로세스 기반 검색 (방법 설명)
            return self._process_based_search(question, entities, limit)
        else:
            # 의미 기반 검색 (일반)
            return self.search(question, limit)
    
    def _metadata_based_search(self, question: str, entities: List[str], limit: int) -> List[QueryResult]:
        """메타데이터 기반 검색"""
        results = []
        
        for doc in self.documents:
            score = 0
            
            # 엔티티 매칭
            for entity in entities:
                if entity == 'database_table' and doc.metadata.get('table_name'):
                    score += 2
                elif entity == 'api_endpoint' and doc.metadata.get('api_endpoint'):
                    score += 2
                elif entity == 'controller' and 'controller' in doc.category:
                    score += 2
                elif entity == 'service' and 'service' in doc.category:
                    score += 2
                elif entity == 'database_model' and 'database_model' in doc.category:
                    score += 2
            
            # 파일명 매칭
            if any(keyword in doc.file_path.lower() for keyword in question.lower().split()):
                score += 1
            
            if score > 0:
                results.append(QueryResult(
                    document=doc,
                    score=score,
                    matched_sections=[doc.metadata.get('original_content', doc.content)]
                ))
        
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]
    
    def _process_based_search(self, question: str, entities: List[str], limit: int) -> List[QueryResult]:
        """프로세스 기반 검색"""
        # 함수, API 엔드포인트, 서비스 로직 중심으로 검색
        results = []
        
        for doc in self.documents:
            score = 0
            
            # 프로세스 관련 청크 타입 우선
            if doc.metadata.get('chunk_type') in ['function', 'api_endpoint', 'service']:
                score += 3
            
            # 엔티티 매칭
            for entity in entities:
                if entity in doc.category:
                    score += 2
            
            # 키워드 매칭
            question_words = question.lower().split()
            content_lower = doc.content.lower()
            score += sum(1 for word in question_words if word in content_lower)
            
            if score > 0:
                results.append(QueryResult(
                    document=doc,
                    score=score,
                    matched_sections=[doc.metadata.get('original_content', doc.content)]
                ))
        
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]
    
    def _get_system_prompt(self, question_analysis: Dict) -> str:
        """질문 유형에 따른 시스템 프롬프트 생성"""
        base_prompt = "당신은 sabangnet_API 전자상거래 시스템의 전문가입니다. 주어진 코드와 문서를 바탕으로 정확하고 유용한 답변을 제공해주세요. 답변은 한국어로 작성하고, 구체적인 예시나 단계별 설명을 포함해주세요."
        
        if question_analysis['type'] == 'how_to':
            return base_prompt + "\n\n특히 프로세스나 방법에 대한 질문이므로 단계별로 자세히 설명해주세요."
        elif question_analysis['type'] == 'location':
            return base_prompt + "\n\n특히 파일 위치나 구조에 대한 질문이므로 정확한 경로와 위치를 명시해주세요."
        elif question_analysis['type'] == 'what_is':
            return base_prompt + "\n\n특히 정의나 구조에 대한 질문이므로 명확하고 상세한 설명을 제공해주세요."
        else:
            return base_prompt
    
    def _generate_fallback_answer(self, question: str, context: str) -> str:
        """GPT 없을 때 폴백 답변 생성"""
        return f"""
질문: {question}

관련 정보:
{context}

참고: 위 정보는 sabangnet_API 코드베이스에서 추출된 내용입니다.
더 자세한 정보가 필요하면 해당 파일을 직접 확인해주세요.
        """.strip()
    
    def get_statistics(self) -> Dict[str, Any]:
        """시스템 통계 정보"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 총 문서 수
        cursor.execute('SELECT COUNT(*) FROM documents')
        total_docs = cursor.fetchone()[0]
        
        # 카테고리별 문서 수
        cursor.execute('SELECT category, COUNT(*) FROM documents GROUP BY category')
        category_stats = dict(cursor.fetchall())
        
        conn.close()
        
        return {
            "total_documents": total_docs,
            "category_statistics": category_stats,
            "vector_available": False,
            "faiss_index_built": False,
            "gpt_available": self.openai_client is not None,
            "search_mode": "GPT 기반 검색"
        }

# 실시간 질문-답변 시스템
class InteractiveQASystem:
    """실시간 질문-답변 시스템"""
    
    def __init__(self, rag_system: SabangnetRAGSystem):
        self.rag = rag_system
    
    def start_interactive_mode(self):
        """대화형 모드 시작"""
        print("🚀 sabangnet_API RAG 시스템 시작")
        print("=" * 60)
        print("💡 사용법:")
        print("  - sabangnet_API에 대한 어떤 질문이든 자유롭게 입력하세요")
        print("  - 예: '주문 데이터는 어떻게 처리되나요?', '상품 등록 API는 어디에 있나요?'")
        print("  - 종료하려면 'quit', 'exit', '종료'를 입력하세요")
        print("=" * 60)
        
        while True:
            try:
                question = input("\n❓ 질문을 입력하세요: ").strip()
                
                if question.lower() in ['quit', 'exit', '종료']:
                    print("👋 RAG 시스템을 종료합니다.")
                    break
                
                if not question:
                    continue
                
                print("\n🔍 검색 중...")
                answer = self.rag.answer_question(question)
                print(f"\n💡 답변:\n{answer}")
                print("-" * 60)
                
            except KeyboardInterrupt:
                print("\n\n👋 RAG 시스템을 종료합니다.")
                break
            except Exception as e:
                print(f"\n❌ 오류 발생: {e}")
    
    def demo_questions(self):
        """데모 질문들로 시스템 테스트"""
        demo_questions = [
            "데이터베이스는 어떻게 구성되어 있나요?",
            "주문 관련 컨트롤러는 어떻게 작동하나요?",
            "지마켓에 물건을 보내려면 어떤 API를 써야 하나요?",
            "배치 작업은 어떻게 구현되어 있나요?",
            "스마일배송 주문 데이터는 어떻게 처리되나요?"
        ]
        
        print("🧪 데모 질문으로 시스템 테스트")
        print("=" * 60)
        
        for i, question in enumerate(demo_questions, 1):
            print(f"\n[{i}/{len(demo_questions)}] 질문: {question}")
            print("-" * 40)
            
            answer = self.rag.answer_question(question)
            print(f"답변: {answer}")
            print("=" * 60)

# 사용 예시
if __name__ == "__main__":
    # RAG 시스템 초기화
    rag = SabangnetRAGSystem()
    
    # sabangnet_API에서 문서 추출
    rag.extract_sabangnet_documents()
    
    # Faiss 인덱스 재구축
    rag._build_faiss_index()
    
    # 통계 정보 출력
    stats = rag.get_statistics()
    print(f"시스템 통계: {stats}")

    # 실시간 질문-답변 시스템 시작
    qa_system = InteractiveQASystem(rag)
    qa_system.start_interactive_mode()
