import { createRoot } from 'react-dom/client';
import { useState, useEffect } from 'react';

const root = createRoot(document.getElementById('root'));

function ChatSidebar(){
    const [chatList, setChatList] = useState([])

    useEffect(() => {
        async function loadChats() {
            const response = await fetch('http://127.0.0.1:8000/api/chats');
            const data = await response.json();
            setChatList(data)
        }

        loadChats();
    }, []);
    
    return(
        <aside>
                {chatList.map((chat) =>(
                    <section key={chat.id} className='chat-section'>
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

function ChatMessageBox(){
    const [text, setText] = UseState("");

    const handleSubmit = async (event) => {
        event.preventDefault();
        const data = {text};

        try{
            const reponse = await fetch('https://api.example.com/users', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            });
        }
        catch{
            
        }
    }
    return(
        <section>
            <form onSubmit={handleSubmit()}> 
                <input 
                    type="text" 
                    value={text} 
                    placeholder='Type your message here' 
                    onChange={(e) => setText(e.target.value)}
                />
                <button type="submit">Send</button>
            </form>
        </section>
    )
}
root.render(<ChatSidebar />);