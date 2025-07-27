import { useState, useEffect, useRef } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { atomDark } from 'react-syntax-highlighter/dist/esm/styles/prism';

import './App.css';
import LoadingGif from './load.gif';
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
import { styled } from '@mui/material/styles';
import Tooltip, { tooltipClasses } from '@mui/material/Tooltip';
import Logo from './logo.png'

function Load({showHis}){
  return (
    <div className={`load-page ${showHis&&"shrinked-load-page"}`}>
      <p>Loading...</p>
      <img className='load-gif' src={LoadingGif}/>
    </div>
  );
}

export default function App() {
  const [history, setHistory]=useState(JSON.parse(localStorage.getItem("history"))||[]);
  const [historyId, setHistoryId]=useState(JSON.parse(localStorage.getItem("historyId"))||[]);
  const [currHist, setCurrHist]=useState(-1);
  const [showHis, setShowHis]=useState(false);
  const [login,setLogin]=useState(localStorage.getItem('history')?2:0);
  const [load,setLoad]=useState(false);
  const [sessionId, setSessionId]=useState(getSessionId());

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

  const BootstrapTooltip = styled(({ className, ...props }) => (
    <Tooltip {...props} arrow classes={{ popper: className }} />
  ))(({ theme }) => ({
    [`& .${tooltipClasses.arrow}`]: {
      color: theme.palette.common.black,
    },
    [`& .${tooltipClasses.tooltip}`]: {
      backgroundColor: theme.palette.common.black,
      fontSize: '14px'
    },
  }));

  function getSessionId() {
    let sessionId = localStorage.getItem("session_id");
    if (!sessionId) {
      const sessionId = uuidv4();
      localStorage.setItem("session_id", sessionId);
    }
    return sessionId;
  }

  async function fetchReply(userText, apiUrl) {
    try {
      const res = await fetch(apiUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, query: userText }),
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
    setLoad(true);
    if(messages.length===0)
    {
      setLoad(false);
      return;
    }
    e?.preventDefault();
    const summary=await fetchReply(JSON.stringify({"chat_id": currHist===-1?-1:historyId[currHist],"username":localStorage.getItem("username"), "messages":messages, "saved_yb_yamls":saved_yb_yaml, "saved_pg_yamls":saved_pg_yaml}),"http://localhost:3032/refresh");
    console.log("get");
    console.log(summary);
    if(summary.chat_id.success)
    {
      setSavedYbYaml([]);
      setSavedPgYaml([]);
      setYAMLMessageId(null);
      setShowYAML(0);
      setQuery('');
      setMessages([]);
      setCurrHist(-1);
      if (summary?.chat_id?.data != null && !historyId.includes(summary.chat_id.data)) {
        setHistory((prev) => [summary.text, ...prev]);
        setHistoryId((prev) => [summary.chat_id.data, ...prev]);
      }
    }
    setLoad(false);
  }
  
  async function openChat(indx) {
    setLoad(true);
    console.log(currHist,historyId[currHist]);
    var output;
    var len=messages.length;
    if(len!==0)
    {
      setSessionId(historyId[indx]);
      output=await fetchReply(JSON.stringify({"chat_id": currHist===-1?-1:historyId[currHist],"username":localStorage.getItem("username"), "messages":messages, "saved_yb_yamls":saved_yb_yaml, "saved_pg_yamls":saved_pg_yaml}),"http://localhost:3032/refresh");
    }
    if(indx===-1){
      setCurrHist(-1);
      setSavedYbYaml([]);
      setSavedPgYaml([]);
      setYAMLMessageId(null);
      setShowYAML(0);
      setQuery('');
      setMessages([]);
      setLoad(false);
      return;
    }
    const summary=await fetchReply(historyId[indx],"http://localhost:3032/open-chat");
    if (output?.chat_id?.data != null && !historyId.includes(output.chat_id.data)) {
      setHistory((prev) => [output.text, ...prev]);
      setHistoryId((prev) => [output.chat_id.data, ...prev]);
    }
    if(summary.success)
    {
      if(summary.data?.length!==0)
      {
        setMessages(summary.data[0][0]);
        setSavedPgYaml(summary.data[0][2]);
        setSavedYbYaml(summary.data[0][1]);
        setCurrHist(indx);
      }
    }
    currHist===-1 && len>0?setCurrHist(indx+1):setCurrHist(indx);
    setLoad(false);
  }

  async function handleLogin(e){
    e.preventDefault();
    setLoad(true);
    const summary=await fetchReply(JSON.stringify({ username:username, password:password }),"http://localhost:3032/login");
    console.log(summary);
    if(summary?.success)
    {
      localStorage.setItem("username",username);
      setLogin(2);
      const data = summary?.data || [];

      const tempHistory = [];
      const tempHistoryId = [];

      data.forEach(innerList => {
        tempHistory.unshift(innerList[1]);
        tempHistoryId.unshift(innerList[0]);
      });

      setHistory(tempHistory);
      setHistoryId(tempHistoryId);
      localStorage.setItem("history",JSON.stringify(tempHistory));
      localStorage.setItem("historyId",JSON.stringify(tempHistoryId));
    }
    setLoad(false);
  }

  async function handleLogout(e){
    e.preventDefault();
    setLoad(true);
    if(messages.length>0)
    await fetchReply(JSON.stringify({"chat_id": currHist===-1?-1:historyId[currHist],"username":localStorage.getItem("username"), "messages":messages, "saved_yb_yamls":saved_yb_yaml, "saved_pg_yamls":saved_pg_yaml}),"http://localhost:3032/refresh");
    setLogin(0);
    setCurrHist(-1); 
    setShowYAML(0);
    setQuery('');
    setMessages([]);
    setYAMLMessageId(null);
    setSavedPgYaml([]);
    setSavedYbYaml([]);
    localStorage.removeItem('username');
    localStorage.removeItem("history");
    localStorage.removeItem("historyId");
    setHistory([]);
    setHistoryId([]); 
    setLoad(false);
  }

  function LinkifyText({ text }) {
    const linkRegex = /(\bhttps?:\/\/[^\s]+)/g;
    const parts = text.split(linkRegex);
    return (
      <>
        {parts.map((part, i) =>
          linkRegex.test(part) ? (
            <a key={i} href={part} target="_blank" rel="noopener noreferrer" className="text-blue-500 underline">
              {part}
            </a>
          ) : (
            <code key={i}>{part}</code>
          )
        )}
      </>
    );
  }
  

  return (
    <div className='App'>
      <div className='sidebar'>
        <div className='icons'>
          <div className='usable-icons'>
            <img src={Logo} style={{width:"50px"}}/>
            <BootstrapTooltip title="Show History" arrow placement="right"><BsWindowFullscreen style={{height:"30px",width:"30px", cursor:"pointer"}} onClick={()=>setShowHis(!showHis)}/></BootstrapTooltip>
            <BootstrapTooltip title="New Chat" arrow placement="right"><button onClick={handleRefresh} disabled={messages.length < 2} style={{ background: "none", border: "none", padding: 0, cursor:"pointer"}}>
              <FaCirclePlus style={{ height: "30px", width: "30px", color: messages.length === 0 ? "gray" : "black", cursor:"pointer" }} />
            </button></BootstrapTooltip>
            <BootstrapTooltip title="Perf Service" arrow placement="right"><FaLocationArrow style={{height:"30px",width:"30px", cursor:"pointer"}} onClick={() => window.open("http://10.9.0.179/dashboard", "_blank")}/></BootstrapTooltip>
          </div>
          <div className='control-icons'>
            
            {login===0?<BootstrapTooltip title="LOGIN" arrow placement="right"><IoLogIn style={{height:"30px",width:"30px", cursor:"pointer"}} onClick={()=>setLogin(1)}/></BootstrapTooltip>:login===1?<BootstrapTooltip title="CHAT" arrow placement="right"><BsFillChatTextFill style={{height:"30px",width:"30px", cursor:"pointer"}} onClick={()=>setLogin(0)}/></BootstrapTooltip>:<BootstrapTooltip title="LOGOUT" arrow placement="right"><IoLogOut style={{height:"30px",width:"30px", cursor:"pointer"}} onClick={handleLogout}/></BootstrapTooltip>}
          </div>
        </div>
      </div>
      <div className={`history ${!showHis&&"hidden"}`}>
          <div className={`history-tabs new-chat ${currHist===-1&&"current-hist"}`} onClick={()=>openChat(-1)} key={-1} disabled={messages.length<2}>New Chat</div>
          {history.map((m,i)=>{
            return <div className={`history-tabs ${currHist===i&&"current-hist"}`} onClick={()=>openChat(i)} key={i}>{m}</div>
          })}
      </div>
      {load?<Load showHis={showHis}/>:
      <div className={`main ${showHis&&"shrinked"}`}>
        {login===1?
        <div className='login-page'>
          <div className='login-main'>
            <h1>Login to <span style={{color:"#22808d"}}>PerfGenie</span></h1>
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
                          <LinkifyText text={m.text} />
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
                {/* <p onClick={handleRefresh}>Create Some Magic</p> */}
                <button type='submit' onClick={handleSubmit} className='search-submit-btn'>Generate</button>
              </div>
            </form>
          </div>
        </>
        :<>
          <h1>Welcome to <span style={{color:"#22808d"}}>PerfGenie</span></h1>
            <form className='search-box' onSubmit={handleSubmit}>
              <input type='text' placeholder='Type your Query...' className='search-ip' onChange={(e) => setQuery(e.target.value)} required/>
              <div className='search-submit'>
                {/* <p onClick={handleRefresh}>Create Some Magic</p> */}
                <button type='submit' onClick={handleSubmit} className='search-submit-btn'>Generate</button>
              </div>
            </form>
        </>}
      </div>}
    </div>
  );
}
