#!/usr/bin/env python3
"""
sabangnet_API RAG 시스템 실행 스크립트
"""

import sys
import os
from pathlib import Path

# 현재 디렉토리를 Python 경로에 추가
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))

from rag_system import SabangnetRAGSystem, InteractiveQASystem

def main():
    print("🚀 sabangnet_API RAG 시스템 시작")
    print("=" * 60)
    
    # RAG 시스템 초기화
    print("📚 RAG 시스템 초기화 중...")
    rag = SabangnetRAGSystem()
    
    # sabangnet_API에서 문서 추출
    print("📖 sabangnet_API 문서 추출 중...")
    rag.extract_sabangnet_documents()
    
    # GPT 기반 검색 모드 - 인덱스 구축 불필요
    print("🔍 GPT 기반 검색 모드 활성화")
    
    # 통계 정보 출력
    stats = rag.get_statistics()
    print("\n📊 시스템 통계:")
    print(f"  - 총 문서 수: {stats['total_documents']}")
    print(f"  - 검색 모드: {stats['search_mode']}")
    print(f"  - GPT API 사용 가능: {stats['gpt_available']}")
    print(f"  - 카테고리별 문서 수: {stats['category_statistics']}")
    
    # 실시간 질문-답변 시스템 시작
    qa_system = InteractiveQASystem(rag)
    qa_system.start_interactive_mode()

def test_mode():
    """테스트 모드 - 데모 질문들로 시스템 테스트"""
    print("🧪 테스트 모드 시작")
    print("=" * 60)
    
    # RAG 시스템 초기화
    rag = SabangnetRAGSystem()
    
    # 문서 추출
    rag.extract_sabangnet_documents()
    
    # 데모 질문으로 테스트
    qa_system = InteractiveQASystem(rag)
    qa_system.demo_questions()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_mode()
    else:
        main()
