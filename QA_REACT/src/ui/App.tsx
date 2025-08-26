import React, { useEffect, useMemo, useRef, useState } from "react";
import ReconnectingWebSocket from "reconnecting-websocket";
import { Toaster, toast } from "react-hot-toast";

type ChatEvent =
  | { type: "joined"; roomId: number }
  | { type: "ack"; data: any }
  | { type: "message"; data: any }
  | { type: "error"; message?: string };

type MessageItem = {
  id: number;
  roomId: number;
  senderId: number;
  toUserId: number | null;
  content: string;
  seq: number;
  createdAt?: string;
  replyToId?: number | null;
  source?: "ws" | "sse";
};

export const App: React.FC = () => {
  const [roomId, setRoomId] = useState<number>(1);
  const [userId, setUserId] = useState<number | null>(null);
  const [username, setUsername] = useState<string>("");
  const [toUserId, setToUserId] = useState<number>(2);
  const [content, setContent] = useState("");
  const [logs, setLogs] = useState<string[]>([]);
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [sseMessages, setSseMessages] = useState<MessageItem[]>([]);

  const wsRef = useRef<ReconnectingWebSocket | null>(null);
  const sseRef = useRef<EventSource | null>(null);

  const wsUrl = useMemo(() => {
    const base = location.origin.replace(/^http/, "ws");
    return `${base}/ws`;
  }, []);

  useEffect(() => {
    if (userId == null) return;
    const ws = new ReconnectingWebSocket(wsUrl);
    wsRef.current = ws;
    ws.addEventListener("open", () => setLogs((l) => ["[WS] connected", ...l]));
    ws.addEventListener("close", () => setLogs((l) => ["[WS] closed", ...l]));
    ws.addEventListener("error", () => setLogs((l) => ["[WS] error", ...l]));
    ws.addEventListener("message", (e) => {
      console.log("[WS:onmessage]", e.data);
      setLogs((l) => ["[WS] <= " + e.data, ...l]);
      try {
        const msg: ChatEvent = JSON.parse(String(e.data));
        const upsert = (m: MessageItem) =>
          setMessages((arr) => {
            const i = arr.findIndex((x) => x.id === m.id);
            if (i !== -1) return arr.map((x, idx) => (idx === i ? { ...x, ...m } : x));
            return [...arr, m];
          });
        if (msg.type === "ack" && (msg as any).data) {
          const m = { ...(msg as any).data, source: "ws" } as MessageItem;
          if (m.roomId === roomId) upsert(m);
        } else if (msg.type === "message" && (msg as any).data) {
          const m = { ...(msg as any).data, source: "ws" } as MessageItem;
          if (m.roomId === roomId) upsert(m);
        }
      } catch {}
    });
    return () => ws.close();
  }, [wsUrl, userId, roomId]);

  // WS 오픈/room 변경 시 자동 조인 보장
  useEffect(() => {
    if (!wsRef.current || userId == null) return;
    const ws = wsRef.current;
    const tryJoin = () => {
      try {
        ws.send(JSON.stringify({ type: "join_room", roomId }));
        console.log("[WS] auto join_room", roomId);
        setLogs((l) => ["[WS] auto join_room " + roomId, ...l]);
      } catch (e) {}
    };
    if (ws.readyState === 1) tryJoin();
    else {
      const onOpen = () => {
        tryJoin();
        ws.removeEventListener("open", onOpen as any);
      };
      ws.addEventListener("open", onOpen as any);
    }
  }, [roomId, userId]);

  useEffect(() => {
    if (userId == null) return;
    const es = new EventSource(`/sse/rooms/${roomId}?toUserId=${userId}`);
    sseRef.current = es;
    es.onopen = () => setLogs((l) => ["[SSE] subscribed", ...l]);
    es.onmessage = (e) => {
      console.log("[SSE:onmessage]", e.data);
      setLogs((l) => ["[SSE] <= " + e.data, ...l]);
      try {
        const data = { ...(JSON.parse(e.data) as MessageItem), source: "sse" } as MessageItem;
        if (data.roomId === roomId) {
          setMessages((arr) => (arr.some((x) => x.id === data.id) ? arr : [...arr, data]));
          setSseMessages((arr) => (arr.some((x) => x.id === data.id) ? arr : [...arr, data]));
          toast.success(`새 메시지: ${data.content}`);
        }
      } catch {}
    };
    es.onerror = () => setLogs((l) => ["[SSE] error", ...l]);
    return () => es.close();
  }, [roomId, userId]);

  // 히스토리 로드 (로그인 또는 room 변경 시)
  useEffect(() => {
    if (userId == null) return;
    (async () => {
      try {
        const res = await fetch(`/api/chat/rooms/${roomId}/history?limit=50`);
        if (!res.ok) throw new Error("history_fail");
        const data = await res.json();
        setMessages(data.items ?? []);
      } catch (e) {
        setLogs((l) => ["[HISTORY] load fail", ...l]);
      }
    })();
  }, [roomId, userId]);

  const joinRoom = () => {
    wsRef.current?.send(JSON.stringify({ type: "join_room", roomId }));
  };

  const publish = () => {
    if (userId == null) {
      setLogs((l) => ["[APP] login first", ...l]);
      return;
    }
    wsRef.current?.send(
      JSON.stringify({
        type: "publish",
        roomId,
        senderId: userId,
        toUserId,
        content,
      })
    );
    setContent("");
  };

  const login = async () => {
    try {
      const res = await fetch(`/api/user/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username }),
      });
      const data = await res.json();
      if (res.ok && data?.userId) {
        setUserId(data.userId);
        setLogs((l) => ["[AUTH] login ok userId=" + data.userId, ...l]);
      } else {
        setLogs((l) => ["[AUTH] login failed", ...l]);
      }
    } catch (e) {
      setLogs((l) => ["[AUTH] login error", ...l]);
    }
  };

  return (
    <div style={{ padding: 16, fontFamily: "system-ui, sans-serif" }}>
      <Toaster position="top-right" />
      <h3>QA React Chat</h3>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="username"
        />
        <button onClick={login}>Login</button>
        <span>userId: {userId ?? "-"}</span>
      </div>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <label>
          roomId
          <input value={roomId} onChange={(e) => setRoomId(Number(e.target.value || 0))} type="number" style={{ marginLeft: 6 }} />
        </label>
        <label>
          userId
          <input value={userId ?? ""} onChange={(e) => setUserId(Number(e.target.value || 0))} type="number" style={{ marginLeft: 6 }} />
        </label>
        <label>
          toUserId
          <input value={toUserId} onChange={(e) => setToUserId(Number(e.target.value || 0))} type="number" style={{ marginLeft: 6 }} />
        </label>
        <button onClick={joinRoom}>Join</button>
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <input
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="message"
          style={{ flex: 1 }}
        />
        <button onClick={publish}>Send</button>
      </div>

      <div>
        <h4>Messages</h4>
        <div style={{ background: "#f5f5f5", padding: 12, maxHeight: 240, overflow: "auto", marginBottom: 12 }}>
          {messages.map((m) => (
            <div key={m.id} style={{ padding: "6px 0", borderBottom: "1px solid #e5e5e5" }}>
              <b>#{m.seq}</b> [room {m.roomId}] <b>{m.senderId}</b>: {m.content}
            </div>
          ))}
        </div>
        <h4>SSE</h4>
        <div style={{ background: "#eef9ff", padding: 12, maxHeight: 180, overflow: "auto", marginBottom: 12 }}>
          {sseMessages.map((m) => (
            <div key={m.id} style={{ padding: "6px 0", borderBottom: "1px solid #d7eefc" }}>
              <b>#{m.seq}</b> [room {m.roomId}] <b>{m.senderId}</b>: {m.content}
            </div>
          ))}
          {sseMessages.length === 0 && <div style={{ opacity: 0.6 }}>SSE 수신 대기중...</div>}
        </div>
        <h4>Logs</h4>
        <pre style={{ background: "#111", color: "#0f0", padding: 12, maxHeight: 300, overflow: "auto" }}>
          {logs.join("\n")}
        </pre>
      </div>
    </div>
  );
};


