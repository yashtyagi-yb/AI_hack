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
import { IoIosRocket } from "react-icons/io";
import { GiElephant } from "react-icons/gi";
import { BsFillChatTextFill } from "react-icons/bs";
import { IoLogOut } from "react-icons/io5";

export default function App() {
  const [history, setHistory]=useState([]);
  const [currHist, setCurrHist]=useState(-1);
  const [showHis, setShowHis]=useState(false);
  const [login,setLogin]=useState(0);

  const [username,setUsername] = useState("");
  const [password,setPassword] = useState("");

  const [messages, setMessages] = useState([]);
  const [saved_yb_yaml, setSavedYbYaml] = useState([]);
  const [saved_pg_yaml, setSavedPgYaml] = useState([]);
  const [yamlMessageId, setYAMLMessageId] = useState(null);
  const [showYAML, setShowYAML]=useState(0);
  const [query, setQuery] = useState("");
  const chatEndRef = useRef(null);

  console.log(saved_yb_yaml);

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
      return data;
    } catch (err) {
      console.error(err);
      return "Sorry, I couldn't reach the server.";
    }
  }
  
  console.log(username,password);

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
    const reply = await fetchReply(query,"http://localhost:3032/gen_yaml");
    setMessages((prev) =>
      prev.map((msg) =>
        msg.id === loadingId ? { ...msg, text: reply.text } : msg
      )
    );
    setSavedYbYaml((prev) => {
      if (reply.yb_yaml!=='') {
        return [...prev, reply.yb_yaml];
      } else if (prev.length > 0) {
        return [...prev, prev[prev.length - 1]];
      } else {
        return [...prev, "No YAML Present"];
      }
    });
    setSavedPgYaml((prev) => {
      if (reply.pg_yaml!=='') {
        return [...prev, reply.pg_yaml];
      } else if (prev.length > 0) {
        return [...prev, prev[prev.length - 1]];
      } else {
        return [...prev, "No YAML Present"];
      }
    });
  }  

  async function handleRefresh(e) {
    e.preventDefault();
    const summary=login==2?null:await fetchReply(JSON.stringify({"username":localStorage.getItem("username"), "messages":messages, "saved_yb_yamls":saved_yb_yaml, "saved_pg_yamls":saved_pg_yaml}),"http://localhost:3032/refresh");
    setSavedYbYaml([]);
    setSavedPgYaml([]);
    setYAMLMessageId(null);
    setShowYAML(0);
    setQuery('');
    setMessages([]);
    setHistory((prev) =>
      [summary?.text, ...prev]
    );
  }

  async function handleLogin(e){
    e.preventDefault();
    const summary=await fetchReply(JSON.stringify({ username:username, password:password }),"http://localhost:3032/login");
    if(summary.success)
    {
      localStorage.setItem("username",username);
      setLogin(2);
      setUsername('');
      setPassword('');
      if(summary.data?.length!==0)
      {
        const msgs = summary.data[0][1].replace(/'/g, '"');
        console.log(JSON.parse(msgs));
      }
    }
  }

  return (
    <div className='App'>
      <div className='sidebar'>
        <div className='icons'>
          <div className='usable-icons'>
            <GiMagicLamp style={{height:"50px",width:"50px", marginBottom:"20%"}}/>
            <BsWindowFullscreen style={{height:"30px",width:"30px", cursor:"pointer"}} onClick={()=>setShowHis(!showHis)}/>
            <button onClick={handleRefresh} disabled={messages.length === 0} style={{ background: "none", border: "none", padding: 0, cursor:"pointer"}}>
              <FaCirclePlus style={{ height: "30px", width: "30px", color: messages.length === 0 ? "gray" : "black", cursor:"pointer" }} />
            </button>
            <FaLocationArrow style={{height:"30px",width:"30px", cursor:"pointer"}}/>
          </div>
          <div className='control-icons'>
            {login===0?<IoLogIn style={{height:"30px",width:"30px", cursor:"pointer"}} onClick={()=>setLogin(1)}/>:login==1?<BsFillChatTextFill style={{height:"30px",width:"30px", cursor:"pointer"}} onClick={()=>setLogin(0)}/>:<IoLogOut style={{height:"30px",width:"30px", cursor:"pointer"}} onClick={(e)=>{handleRefresh(e);setLogin(0);setHistory([])}}/>}
          </div>
        </div>
      </div>
      <div className={`history ${!showHis&&"hidden"}`}>
          <div className={`history-tabs ${currHist===-1&&"current-hist"}`} tabindex="0">Current Chat</div>
          {history.map((m,i)=>{
            return <div className={`history-tabs ${currHist===i&&"current-hist"}`} key={i}>{m}</div>
          })}
      </div>
      <div className={`main ${showHis&&"shrinked"}`}>
        {login===1?
        <div className='login-page'>
          <div className='login-main'>
            <h1>Login to Start <span style={{color:"#22808d"}}>Workloading...</span></h1>
            <form className='login-form' onSubmit={handleLogin}>
              <input className='username' type='username' placeholder='Enter Username' value={username} onChange={(e)=>setUsername(e.target.value)} required/>
              <input className='password' type='password' placeholder='Enter Password' value={password} onChange={(e)=>setPassword(e.target.value)} required/>
              <button className='login-submit-btn' type='submit'>Login</button>
            </form>
          </div>
        </div>
        :
        messages.length?
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
                        <IoIosText className={!showYAML && 'active'} onClick={()=>setShowYAML(0)}/>
                        <IoIosRocket className={showYAML===1 && yamlMessageId===i && 'active'} onClick={()=>{setShowYAML(1); setYAMLMessageId(i)}}/>
                        <GiElephant className={showYAML===2 && yamlMessageId===i && 'active'} onClick={()=>{setShowYAML(2); setYAMLMessageId(i)}}/>
                      </div>
                      {showYAML&&yamlMessageId===i?
                        <SyntaxHighlighter language="yaml" style={atomDark}>
                          {showYAML===1?saved_yb_yaml[Math.floor(i/2)]:saved_pg_yaml[Math.floor(i/2)]}
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
              <input type='text' placeholder='Type your Query...' className='search-ip' value={query} onChange={(e) => setQuery(e.target.value)} required/>
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
