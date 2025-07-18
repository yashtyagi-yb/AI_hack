import { useState, useRef, useEffect } from "react";
import "./App.css";

export default function App() {
  const [messages, setMessages] = useState([]);
  const [query, setQuery] = useState("");
  const chatEndRef = useRef(null);
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function fetchReply(userText) {
    const apiUrl = "http://172.151.18.106:3030/gen_yaml";
    try {
      const res = await fetch(apiUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: userText }),
      });
      if (!res.ok) throw new Error(res.statusText);
  
      const yaml = await res.text();
      return yaml;
    } catch (err) {
      console.error(err);
      return "Sorry, I couldn't reach the server.";
    }
  }
  

  async function handleSubmit(e) {
    e.preventDefault();
    if (!query.trim()) return;
    setMessages((prev) => [...prev, { role: "user", text: query }]);
    setQuery("");
    const loadingId = Date.now();
    setMessages((prev) => [...prev, { role: "bot", text: "Analysing...", id: loadingId }]);
    await new Promise((r) => setTimeout(r, 500));
    setMessages((prev) =>
      prev.map((msg) =>
        msg.id === loadingId ? { ...msg, text: "Generating..." } : msg
      )
    );
    await new Promise((r) => setTimeout(r, 500));
    setMessages((prev) =>
      prev.map((msg) =>
        msg.id === loadingId ? { ...msg, text: "Running..." } : msg
      )
    );
    const reply = await fetchReply(query);
    setMessages((prev) =>
      prev.map((msg) =>
        msg.id === loadingId ? { ...msg, text: reply } : msg
      )
    );
  }  

  return (
    <div className="main">
      <div className="header">Welcome to PerfGenie</div>
      <div className="chatbox">
        <div className="chat-area">
          {messages.map((m, i) => (
            <div
              key={i}
              className={m.role === "user" ? "msg user" : "msg bot"}
            >
              {m.role === "bot" ? (
                <pre style={{ whiteSpace: "pre-wrap" }}>
                  <code>{m.text}</code>
                </pre>
                ) : (
                  m.text
              )}
            </div>
          ))}
          <div ref={chatEndRef} />
        </div>

        <div className="input-area">
          <form onSubmit={handleSubmit} className="input-wrapper">
            <input
              className="query"
              type="text"
              placeholder="Enter your query..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <button className="send-btn" type="submit">
              Send
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
