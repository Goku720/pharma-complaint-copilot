import { useRef, useState, useEffect } from "react";
import { useDispatch, useSelector } from "react-redux";
import { sendMessage, uploadDocument, resetSession } from "../store/thunks";

export default function ChatAssistant() {
  const dispatch = useDispatch();
  const messages = useSelector((s) => s.chat.messages);
  const status = useSelector((s) => s.chat.status);
  const [input, setInput] = useState("");
  const fileInputRef = useRef(null);
  const scrollRef = useRef(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, status]);

  const submit = (e) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || status === "loading") return;
    dispatch(sendMessage(text));
    setInput("");
  };

  const onFileChosen = (e) => {
    const file = e.target.files?.[0];
    if (file) dispatch(uploadDocument(file));
    e.target.value = "";
  };

  return (
    <div className="panel chat-panel">
      <div className="panel__header">
        <h2>AIVOA Copilot — AI Assistant</h2>
        <button className="btn btn--ghost btn--small" onClick={() => dispatch(resetSession())} type="button">
          New complaint
        </button>
      </div>

      <div className="chat__messages" ref={scrollRef}>
        {messages.map((m, i) => (
          <div key={i} className={`bubble bubble--${m.role} ${m.isError ? "bubble--error" : ""}`}>
            <div className="bubble__content">{m.content}</div>
            {m.tool_calls?.length ? (
              <div className="bubble__tools">
                {m.tool_calls.map((t, idx) => (
                  <span className="tool-chip" key={idx}>
                    {t}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
        ))}
        {status === "loading" && (
          <div className="bubble bubble--assistant bubble--typing">
            <span className="dot" />
            <span className="dot" />
            <span className="dot" />
          </div>
        )}
      </div>

      <form className="chat__composer" onSubmit={submit}>
        <input
          type="file"
          accept=".pdf,.txt,.eml,.md"
          ref={fileInputRef}
          onChange={onFileChosen}
          hidden
        />
        <button
          type="button"
          className="btn btn--icon"
          title="Upload complaint document (PDF/email)"
          onClick={() => fileInputRef.current?.click()}
        >
          📎
        </button>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="e.g. Apollo Pharmacy reported discolored capsules in Amoxicillin Capsules 500mg"
          disabled={status === "loading"}
        />
        <button type="submit" className="btn btn--primary" disabled={status === "loading" || !input.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}
