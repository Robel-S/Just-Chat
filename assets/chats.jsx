import { createRoot } from 'react-dom/client';
import { useState, useEffect, useRef, useCallback } from 'react';

const root = createRoot(document.getElementById('root'));

//componeent that holds the entire app
function ChatPage(){
    const [chatId, setChatId] = useState(1); //stores id of the current selected chat
    const [user, setUser] = useState(null); //holds the current user thats logged in
    const [messages, setMessages] = useState([]); //holds the list of messages in the selected chat

    const wsRef = useRef(null); //holds the websocket connection and lets it persist outside UseEffect

    //calls the backend api to get and store all the messages of the specificed chat whenver chat changes
    useEffect(() => {
        async function loadMessages() {
            const response = await fetch(`http://127.0.0.1:8000/api/${chatId}/messages`);
            const data = await response.json();
            setMessages(data);
        }
        loadMessages();
    }, [chatId]);

    //opens a websocket connection whenever the chat changes and closes the old one on cleanup
    useEffect(() => {
        const socket = new WebSocket(`ws://127.0.0.1:8000/ws/chat/${chatId}/`); 
        wsRef.current = socket;

        //appends incoming messages to the message list
        socket.onmessage = (event) => {
            setMessages((prev) => [...prev, JSON.parse(event.data)]);
        };
        
        //logs any connection errors to the console
        socket.onerror = (err) => {
            console.error("Websocket error:", err)
        };

        //closes the socket when the component unmounts or chatid changes
        return () => {
            socket.close(1000, "component unmounted")
        };

    }, [chatId]);

    //sends a message over the active Websocket connection as a JSON String
    const send = useCallback((data) => {
        wsRef.current?.send(JSON.stringify(data));
    }, []);

    //calls backend api to get and store current user
    useEffect(() => {
        async function loadUser() {
            const response = await fetch(`http://127.0.0.1:8000/api/me`);
            const data = await response.json();
            setUser(data);
        }
        loadUser();
    }, []);

    return(
        <>
            <ChatSidebar 
                chatId={chatId}
                onSetChat={setChatId}
            /> 
            <div id="message-elems">
                <ChatDisplay chatId={chatId} messages={messages}/>
                <ChatMessageBox chatId={chatId} send={send}/>
            </div>
        </>
    )
}

//display user's chats in a sidebar
function ChatSidebar( {chatId, onSetChat} ){
    const [chatList, setChatList] = useState([]);

    //calls the backend api to get and store all of the users chats
    useEffect(() => {
        async function loadChats() {
            const response = await fetch('http://127.0.0.1:8000/api/chats');
            const data = await response.json();
            setChatList(data);
        }
        loadChats();
    }, []);
    
    return(
        <aside>
                {chatList.map((chat) =>(
                    <section key={chat.id} className={`chat-section ${chatId === chat.id ? "selected" : ""}`} onClick={() => onSetChat(chat.id)}>
                        <img src={chat.image} alt="Test Image"></img>
                        <div className="chat-text">
                            <div className='chat-title'>{chat.name}</div>
                            <div className='chat-last_message'>User: Did you go last night?</div>
                        </div>
                    </section>
                ))}
        </aside>
    )
}

//displays chat messeges in a box
function ChatDisplay({ chatId, messages }){

    return(
        <section id="chatBox">
            {messages.map((message) =>(
                <section key={message.id} className='message'>
                    <p>{message.username}</p>
                    <p>{message.text}</p>
                    <sub>{message.timestamp}</sub>
                </section>
            ))}
        </section>
    )
}

//textbox where user types and sends messages
function ChatMessageBox( {chatId, send} ){
    const [text, setText] = useState(""); //stores current message in the textbox

    //once user submits a message it trims it and sends over the websocket connection in JSON formate
    const handleSubmit = (e) => {
        e.preventDefault()

        if(!text.trim()) return;

        send({
            text: text
        });

        setText("");
    };

    return(
        <section id="message-box">
            <form onSubmit={handleSubmit}> 
                <input 
                    type="text" 
                    value={text} 
                    id="text-box"
                    placeholder='Type your message here' 
                    onChange={(e) => setText(e.target.value)}
                />
                <button type="submit">Send</button>
            </form>
        </section>
    )
}

root.render(
    <>
        <ChatPage />
    </>
)