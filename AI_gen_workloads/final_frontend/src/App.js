import { useState, useEffect, useRef } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { atomDark } from 'react-syntax-highlighter/dist/esm/styles/prism';

import './App.css';
import { BsWindowFullscreen } from "react-icons/bs";
import { GiMagicLamp } from "react-icons/gi";
import { FaCirclePlus } from "react-icons/fa6";
import { FaLocationArrow } from "react-icons/fa";
import { IoLogIn } from "react-icons/io5";
import { IoIosText } from "react-icons/io";
import { FaFileCode } from "react-icons/fa";

export default function App() {
  const [fullScreen, setFull]=useState(false);

  const [messages, setMessages] = useState([]);
  const [yaml,setYAML]=useState("No YAML present");
  const [yamlMessageId, setYAMLMessageId] = useState(null);
  const [showYAML, setShowYAML]=useState(false);
  const [query, setQuery] = useState("");
  const chatEndRef = useRef(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function getSessionId() {
    let sessionId = localStorage.getItem("session_id");
    if (!sessionId) {
      const sessionId = uuidv4();
      localStorage.setItem("session_id", sessionId);
    }
    return sessionId;
  }

  async function fetchReply(userText, apiUrl) {
    const sid=getSessionId();
    try {
      const res = await fetch(apiUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sid, query: userText }),
      });
      if (!res.ok) throw new Error(res.statusText);
  
      const data = await res.json();
      if(data.yaml!='')
      {
        setYAML(data.yaml);
        data.text="Your YAML has been created! Its Executing...";
      }
      return data.text;
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
    const reply = await fetchReply(query,"http://0.0.0.0:3032/gen_yaml");
    setMessages((prev) =>
      prev.map((msg) =>
        msg.id === loadingId ? { ...msg, text: reply } : msg
      )
    );
  }  

  async function handleRefresh(e) {
    e.preventDefault();
    await fetchReply("","http://0.0.0.0:3032/refresh");
  }


  return (
    <div className='App'>
      <div className='sidebar'>
        <div className='icons'>
          <div className='usable-icons'>
            <GiMagicLamp style={{height:"50px",width:"50px", marginBottom:"20%"}}/>
            <BsWindowFullscreen style={{height:"30px",width:"30px"}} onClick={()=>setFull(!fullScreen)}/>
            <FaCirclePlus style={{height:"30px",width:"30px"}}/>
            <FaLocationArrow style={{height:"30px",width:"30px"}}/>
          </div>
          <div className='control-icons'>
            <IoLogIn style={{height:"30px",width:"30px"}}/>
          </div>
        </div>
        <div className='history'></div>
      </div>
      <div className='main'>
        {messages.length?
        <>
          <div className='conversation'>
            <div className='messages'>
              {messages.map((m, i) => (
                <div
                  key={i}
                  className={m.role === "user" ? "msg user" : "msg bot"}
                >
                  {m.role === "bot" ? (
                    <div className='bot-msg' key={m.id}>
                      <div className='bot-msg-icons'>
                        <IoIosText className={!showYAML && 'active'} onClick={()=>setShowYAML(false)}/>
                        <FaFileCode className={showYAML && yamlMessageId==i && 'active'} onClick={()=>{setShowYAML(true); setYAMLMessageId(i)}}/>
                      </div>
                      {showYAML&&yamlMessageId==i?
                        <SyntaxHighlighter language="yaml" style={atomDark}>
                          {yaml}
                        </SyntaxHighlighter>:
                        <pre style={{ whiteSpace: "pre-wrap" }}>
                          <code>{m.text}</code>
                        </pre>}
                    </div>
                    ) : (
                      m.text
                  )}
                </div>
              ))}
              <div ref={chatEndRef} />
            </div>
            <form className='search-box' onSubmit={handleSubmit}>
              <input type='text' placeholder='Type your Query...' className='search-ip' onChange={(e) => setQuery(e.target.value)} required/>
              <div className='search-submit'>
                <p onClick={handleRefresh}>Create Some Magic</p>
                <button type='submit' onClick={handleSubmit} className='search-submit-btn'>Generate</button>
              </div>
            </form>
          </div>
        </>
        :<>
          <h1>Welcome to Perf <span style={{color:"#22808d"}}>Genie</span></h1>
            <form className='search-box' onSubmit={handleSubmit}>
              <input type='text' placeholder='Type your Query...' className='search-ip' onChange={(e) => setQuery(e.target.value)} required/>
              <div className='search-submit'>
                <p onClick={handleRefresh}>Create Some Magic</p>
                <button type='submit' onClick={handleSubmit} className='search-submit-btn'>Generate</button>
              </div>
            </form>
        </>}
      </div>
    </div>
  );
}
