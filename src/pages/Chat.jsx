
import { useState ,useEffect, useRef } from 'react';
import useEffectScroll from '../hooks/useEffectScroll.jsx';
import chatbotStyles from '../chatbot/Chatbot.module.css'
import AutoResizeTextarea from '../hooks/AutoResizeTextarea.jsx';
import ReactMarkdown from "react-markdown";
import { useTranslation } from "react-i18next";
import stylesChat from "../assets/css/Chat.module.css"
const API_URL = import.meta.env.VITE_API_URL;

function Chat() {
    const MAX_REQUEST_LENGTH = 1500;

    const [text, setText] = useState("");
    const [contentIntro, setContent] = useState("");
    const [trigger, setTrigger] = useState("");
    const chatRef = useRef(null);
    const lastMessageRef = useRef(null);
    const { t } = useTranslation();
    
    const {messages, setMessages} = useEffectScroll(trigger);
    
    const handleKey = (e) =>{
        if (e.key === "Enter" && !e.shiftKey){
            e.preventDefault();
            if (text.trim() !== ""){
                setTrigger(text);
                sendMessage(text);
                setText("");
            }
        }
    };



    const sendMessage = async (message) =>{
        try {
            const response = await fetch(`${API_URL}/chatbot`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({message}),
            });
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let fullResponse = "";

            // First, add an empty chatbot message to update later
            setMessages(prev => [...prev, { role: "responses", content: "" }]);

            let done = false;
            while (!done) {
                const { value, done: readerDone } = await reader.read();

                done = readerDone;
                if (value) {
                    const chunk = decoder.decode(value, { stream: true });
                    fullResponse += chunk;

                    // Update the last chatbot message with new chunk
                    setMessages(prev => {
                        const lastMessage = prev[prev.length - 1];
                        if (lastMessage.role === "responses") {
                            const updatedLast = { ...lastMessage, content: fullResponse };
                            return [...prev.slice(0, prev.length - 1), updatedLast];
                        }
                        return prev;
                    });
                }
            }
            setTrigger("");
        } catch (err) {
            console.log("Error sending message: ", err);
        }
    };

    useEffect(() => {
        const es = new EventSource(`${API_URL}/intro-stream`);
        setContent("");

        es.onmessage = (e) => {
            if (e.data === "[DONE]") {
                es.close();
            } else {
                setContent((prev) => prev +" "+ e.data);
            }
        };
        return () => es.close();
    }, []);

    useEffect(() => {
        if (lastMessageRef.current) {
            lastMessageRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
    }, [messages]);


    return (
       <div id={stylesChat.frameSection}>
            <div className= "flex flex-column height-100 jc-space-around">
                <div ref={chatRef} className={stylesChat.frameChat} style={{alignItems:"center"}}> 
                    {messages.length > 0 ? (
                        messages.map((message, idx) => (
                            <div className={chatbotStyles.contentUser} ref={idx === messages.length - 1 ? lastMessageRef : null} key={idx}>
                            {message.role === "id_users" ? (
                                <div className="flex jc-end margin-5-0" style={{paddingLeft:"25%", margin:"18px 0"}}>
                                    <div style={{whiteSpace:"normal", borderRadius:"18px", padding:"5px 14px"}} className={chatbotStyles.id_users}>
                                        {message.content}
                                    </div>
                                </div>
                            ):(
                                <div id  className="flex jc-start margin-0-5">
                                    <div style={{whiteSpace:"normal", padding: "0px 8px", background:"none"}} className={chatbotStyles.responses}>
                                        <ReactMarkdown>{message.content}</ReactMarkdown>
                                    </div>
                                </div>
                            )}
                            </div>
                        ))
                    ):(
                        <div className={chatbotStyles.contentUser} style={{height:"100%", width:"88%", justifyContent:"flex-start", marginTop:"150px"}}>
                            <div className="flex jc-space-between">
                                <div id={stylesChat.framePage} className="flex flex-column margin-0-5">
                                    <h1>{t("chatbot.titleContent")}</h1>
                                    <div className="flex jc-space-between" style={{height: "150px", marginTop:"20px"}}>
                                        <div className="flex flex-column" style={{width: "88%"}}>
                                            <div style={{whiteSpace: "pre-wrap"}}>
                                                <p style={{fontSize:"20px", marginLeft:"0"}}>
                                                    <ReactMarkdown
                                                        components={{
                                                            p: ({node, ...props}) => (
                                                                <p style={{fontSize:"19px", marginBottom:"10px"}} {...props} />
                                                            ),
                                                        }}>
                                                        {contentIntro}
                                                    </ReactMarkdown>
                                                </p>
                                                <div className="flex items-center">
                                                    <p style={{fontSize:"19px"}}>{t("chatbot.question")} </p>
                                                    <span className={chatbotStyles.point_request}></span>
                                                </div>
                                            </div>
                                        </div>
                                        
                                    </div>
                                </div>
                                <div id={stylesChat.chat_img} style={{ height: "235px", width: "266px", borderRadius: "15px"}} 
                                    className="flex jc-center items-center">
                                    <img style={{height:"68%", borderRadius:"15px"}} src="/_logo_QS.svg" alt="" />
                                </div>
                            </div>
                        </div>
                    )}
                </div>
                <div id={stylesChat.frameInput} style={{marginLeft:"20px"}}>
                    <AutoResizeTextarea 
                        value={text}
                        placeholder= {t("chatbot.placeholder")}
                        handleKey = {handleKey}
                        maxLength={MAX_REQUEST_LENGTH}
                        onChange={(e) => {
                            if (e.target.value.length <= MAX_REQUEST_LENGTH) {
                                setText(e.target.value)
                            }
                        }}
                    />
                </div>
            </div>
       </div>
    );
}

export default Chat