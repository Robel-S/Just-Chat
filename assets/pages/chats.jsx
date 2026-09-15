import { createRoot } from 'react-dom/client';
import { useState, useEffect, useRef, useCallback } from 'react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faEllipsisVertical } from '@fortawesome/free-solid-svg-icons';
import { faFileImage, faFile } from '@fortawesome/free-solid-svg-icons';
import { faTimes } from '@fortawesome/free-solid-svg-icons';

/** Return a named cookie value, primarily for Django CSRF requests. */
export function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

/** Build a WebSocket URL using the page's current protocol and host. */
export function getWebSocketUrl(path) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}${path}`;
}

//componeent that holds the entire app
/** Coordinate Chat selection, history, live messages, and unread state. */
export function ChatPage() {
    const [chatId, setChatId] = useState(null); //stores id of the current selected chat
    const [user, setUser] = useState(null); //holds the current user thats logged in
    const [messages, setMessages] = useState([]); //holds the list of messages in the selected chat
    const [chatOwner, setChatOwner] = useState('');
    const [unreadCounts, setUnreadCounts] = useState({});

    const wsRef = useRef(null); //holds the websocket connection and lets it persist outside UseEffect
    const notificationSocket = useRef(null);
    const activeChatIdRef = useRef(null);

    useEffect(() => {
        activeChatIdRef.current = chatId;
    }, [chatId]);

    const markChatAsRead = useCallback(async (activeChatId) => {
        if (!activeChatId) return;

        try {
            const response = await fetch(`/api/chats/${activeChatId}/read/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                },
                credentials: 'same-origin',
            });

            if (!response.ok) {
                throw new Error(`Failed to mark chat as read (${response.status})`);
            }

            setUnreadCounts((prev) => ({ ...prev, [activeChatId]: 0 }));
        } catch (err) {
            console.error("Failed to mark chat as read:", err);
        }
    }, []);

    // 2. Fetch User & Initial Chats Unread Counts
    useEffect(() => {
        /** Load the current user before rendering user-specific Chat data. */
        async function initializeData() {
            try {
                const userRes = await fetch('/api/me', { credentials: 'include' });
                const userData = await userRes.json();
                setUser(userData);

                const chatsRes = await fetch('/api/chats', { credentials: 'include' });
                const chatsData = await chatsRes.json();

                const initialCounts = {};
                chatsData.forEach((chat) => {
                    if (chat.unread_count !== undefined) {
                        initialCounts[chat.id] = chat.unread_count;
                    }
                });

                setUnreadCounts((prev) => ({ ...initialCounts, ...prev }));
            } catch (err) {
                console.error("Initialization error:", err);
            }
        }
        initializeData();
    }, []);
    //calls the backend api to get and store all the messages of the specificed chat whenver chat changes
    useEffect(() => {
        if (!chatId) {
            setMessages([]);
            return;
        }

        /** Load history for the selected Chat and mark it as read. */
        async function loadMessages() {
            const response = await fetch(`/api/${chatId}/messages`);
            const data = await response.json();
            setMessages(data);
        }
        loadMessages();
    }, [chatId]);

    useEffect(() => {
        const socket = new WebSocket(getWebSocketUrl('/ws/notifications/'));
        notificationSocket.current = socket;

        //appends incoming messages to the message list
        socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === "unread_update") {
                setUnreadCounts((prev) => {
                    // Don't update unread count if the chat is currently active
                    if (data.chat_id === activeChatIdRef.current) return prev;
                    return { ...prev, [data.chat_id]: data.unread_count };
                });
            }
        };

        //logs any connection errors to the console
        socket.onerror = (err) => {
            console.error("Notification websocket error:", err)
        };

        //closes the socket when the component unmounts or chatid changes
        return () => {
            socket.close(1000, "component unmounted")
        };

    }, []);

    //opens a websocket connection whenever the chat changes and closes the old one on cleanup
    useEffect(() => {
        if (!chatId) return;

        markChatAsRead(chatId);

        const socket = new WebSocket(getWebSocketUrl(`/ws/chat/${chatId}/`));
        wsRef.current = socket;

        //appends incoming messages to the message list
        socket.onmessage = (event) => {
            setMessages((prev) => [...prev, JSON.parse(event.data)]);
            markChatAsRead(chatId);
        };

        //logs any connection errors to the console
        socket.onerror = (err) => {
            console.error("Websocket error:", err)
        };

        //closes the socket when the component unmounts or chatid changes
        return () => {
            socket.close(1000, "component unmounted")
        };

    }, [chatId, markChatAsRead]);

    //sends a message over the active Websocket connection as a JSON String
    const send = useCallback((data) => {
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
            return false;
        }
        wsRef.current.send(JSON.stringify(data));
        return true;
    }, []);


    return (
        <>
            <ChatSidebar
                chatId={chatId}
                onSetChat={setChatId}
                user={user}
                setChatOwner={setChatOwner}
                unreadCounts={unreadCounts}
            />
            <div id="message-elems">
                <ChatDisplay chatId={chatId} messages={messages} />
                <ChatMessageBox chatId={chatId} send={send} />
            </div>
            <MembersSidebar chatId={chatId} user={user} chatOwner={chatOwner} />
        </>
    )
}

//display user's chats in a sidebar
/** Render the requester's Chats and provide Chat-level actions. */
export function ChatSidebar({ chatId, onSetChat, user, setChatOwner, unreadCounts }) {
    const [chatList, setChatList] = useState([]);
    const [createModal, setCreateModal] = useState(false);
    const [editModal, setEditModal] = useState(false);
    const [openMenuId, setOpenMenuId] = useState(null);

    const csrftoken = getCookie('csrftoken');

    /** Refresh the Chats visible to the current user. */
    async function loadChats() {
        const response = await fetch('/api/chats');
        const data = await response.json();
        setChatList(data);
    }

    useEffect(() => {
        loadChats();
    }, []);


    useEffect(() => {
        /** Close an open Chat menu when a click lands outside it. */
        const handleClickOutside = (event) => {
            if (!event.target.closest('.chat-menu-container')) {
            setOpenMenuId(null); // Close active menu
            }
        };

        document.addEventListener('click', handleClickOutside);
        return () => document.removeEventListener('click', handleClickOutside);
    }, []);

    /** Delete a Chat after the owner confirms the destructive action. */
    async function handleDelete(chatId){
        try{
            await fetch(`/api/chats/${chatId}/`, {
                method: "DELETE",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrftoken,
                },
                credentials: "same-origin",
            });
            loadChats();
        } catch (err) {
            console.error(err);
        }
    }
    /** Remove the current user's membership from a Chat. */
    async function handleLeave(chatId){
        try{
            const response = await fetch(`/api/members/${chatId}/${user.id}/edit/`, {
                method: "DELETE",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrftoken,
                },
                credentials: "same-origin",
            });

            const data = await response.json();

            console.log(data)
            loadChats();
        } catch (err) {
            console.error(err);
        }
    }

    /** Open the edit modal for a selected Chat. */
    function handleEdit(chatId) {
        setEditModal(true);
        setOpenMenuId(null);
    }

    /** Toggle the action menu for a Chat row. */
    function toggleMenu(chat) {
        setOpenMenuId((current) => current === chat.id ? null : chat.id);
    }

    return (
        <>
            <aside>
                <section className='chat-section-header'>
                    <h2 style={{ visibility: "hidden" }}>-</h2>
                    <h2 className='chat-header'>Chats</h2>
                    <button type="button" className='chat-add' aria-label="Create chat" onClick={() => setCreateModal(true)}>+</button>
                </section>
                {chatList.map((chat) => {
                    const count = unreadCounts[chat.id] || 0;
                    return (
                        <section key={chat.id} role="button" tabIndex={0} className={`chat-section ${chatId === chat.id ? "selected" : ""}`} onClick={() => {onSetChat(chat.id); setChatOwner(chat.owner)}} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSetChat(chat.id); setChatOwner(chat.owner); } }}>
                            <img src={chat.image} alt="Test Image" className="chat-img"></img>
                            <div className="chat-text">
                                <div className='chat-title'>{chat.name}</div>
                            </div>
                            {count > 0 && <span className="unread-badge">{count}</span>}
                            <div className="chat-menu-container">
                                <button type="button" aria-label={`Open menu for ${chat.name}`} className="chat-menu-button"
                                    onClick={(e) => {
                                        e.stopPropagation(); // Prevents parent click events (like opening the chat)
                                        toggleMenu(chat);
                                    }}
                                ><FontAwesomeIcon icon={faEllipsisVertical} className="dropdown-icon" /></button>

                                {openMenuId === chat.id && (
                                    <div className="chat-dropdown">
                                        {chat.owner === user?.id && (
                                            <div
                                                className="chat-dropdown-item"
                                                onClick={() => {
                                                    handleEdit(chat.id);
                                                    setOpenMenuId(null);
                                                }}
                                            >
                                                Edit Chat
                                            </div>
                                        )}
                                        {chat.owner === user?.id && (
                                            <div
                                                className="chat-dropdown-item danger"
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleDelete(chat.id);
                                                    setOpenMenuId(null);
                                                }}
                                            >
                                                Delete Chat
                                            </div>
                                        )}
                                        <div
                                            className="chat-dropdown-item danger"
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                handleLeave(chat.id);
                                                setOpenMenuId(null);
                                            }}
                                        >
                                            Leave Chat
                                        </div>
                                    </div>
                                )}
                            </div>
                        </section>
                    );
                })}
            </aside>
            <ChatModal openModal={createModal} setOpenModal={setCreateModal} user={user} onSaved={loadChats} />
            <EditModal openModal={editModal} setOpenModal={setEditModal} user={user} chatId={chatId} onSaved={loadChats}/>
        </>
    )
}

/** Collect Chat details and create a Chat with selected members. */
export function ChatModal({ openModal, setOpenModal, user, onSaved }){
    const [chatName, setChatName] = useState("");
    const [query, setQuery] = useState("");
    const [selectedFriends, setSelectedFriends] = useState([]);
    const [friends, setFriends] = useState([]);
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(false);

    const csrftoken = getCookie('csrftoken');

    useEffect(() => {
        if (openModal) {
            /** Load friends that may be added to the new Chat. */
            async function loadFriends() {
                const response = await fetch('/api/friends');
                const data = await response.json();
                setFriends(data);
            }
            loadFriends();
        }
    }, [openModal]);

    const filteredFriends = friends.filter(friend => {
        if (!user) return false;
        const friendUsername = friend.user_username !== user.username ? friend.user_username : friend.friend_username;
        return friendUsername.toLowerCase().includes(query.toLowerCase());
    });

    /** Add or remove a friend from the pending Chat membership list. */
    const handleFriendSelect = (e) => {
        setSelectedFriends(prev => {
            if (e.target.checked) {
                return [...prev, parseInt(e.target.value)];
            }
            return prev.filter(id => id !== parseInt(e.target.value));
        });
        console.log(selectedFriends);
    }

    /** Create the Chat and then persist its selected memberships. */
    async function handleSubmit(e) {
        e.preventDefault();
        setError(null);

        if (selectedFriends.length === 0) {
            setError("Please select at least one friend to create a chat.");
            return;
        }
        if (selectedFriends.length > 10) {
            setError("You can only add up to 10 friends to a chat.");
            return;
        }

        setLoading(true);
        try {
            const chatType = selectedFriends.length === 1 ? "DM" : "Groupchat";

            const createResponse = await fetch('/api/chats/create', {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrftoken,
                },
                credentials: "same-origin",
                body: JSON.stringify({ name: chatName, chat_type: chatType })
            });

            if (!createResponse.ok) {
                throw new Error("Failed to create chat");
            }

            const newChat = await createResponse.json();
            const chatId = newChat.id;

            const addMembersResponse = await fetch(`/api/chats/${chatId}/members`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrftoken,
                },
                credentials: "same-origin",
                body: JSON.stringify({ members: selectedFriends }),
            });

            if (!addMembersResponse.ok) {
                throw new Error("Failed to add members");
            }
            await onSaved?.();
            closeModal();

        } catch (err) {
            console.log(err)
            setError("Failed to create chat.");
        } finally {
            setLoading(false);
        }
    }

     /** Reset the creation form and close its modal. */
     function closeModal() {
        setOpenModal(false);
        setChatName("");
        setQuery("");
        setFriends([]);
        setSelectedFriends([]);
    }

    return(
        <>
            {openModal &&
                <div className="modal-overlay" onClick={() => closeModal()}>
                    <div className="modal-content" role="dialog" aria-modal="true" aria-labelledby="create-chat-title" onClick={(e) => e.stopPropagation()}>
                        <form onSubmit={handleSubmit}>
                            <h2 id="create-chat-title">Create Chat</h2>
                            <div>
                                <label htmlFor="chat-name" style={{ display: "block", marginBottom: "10px" }}>Chat Name</label>
                                <input
                                    type="text"
                                    id="chat-name"
                                    placeholder="Enter Chat Name"
                                    value={chatName}
                                    onChange={(e) => setChatName(e.target.value)}
                                />
                            </div>
                            <div>
                                <label htmlFor="friend-query" style={{ display: "block", marginBottom: "10px" }}>Add up to 10 Friends</label>
                                <input
                                    type="text"
                                    id="friend-query"
                                    placeholder="Search for friends..."
                                    value={query}
                                    onChange={(e) => setQuery(e.target.value)}
                                />
                                <hr></hr>
                                {loading && <p>Loading...</p>}
                                {error && <p>{error}</p>}
                                {filteredFriends.length > 0 && (
                                    <ul>
                                        {filteredFriends.map((friend) => {
                                            const targetFriendId = friend.user !== user.id ? friend.user : friend.friend;
                                            const targetUsername = friend.user_username !== user.username ? friend.user_username : friend.friend_username;
                                            return (
                                                <li key={friend.id}>
                                                    <label style={{ display: "inline-block" }} htmlFor={`friend-${friend.id}`}>{targetUsername}</label>
                                                    <input
                                                        type="checkbox"
                                                        id={`friend-${friend.id}`}
                                                        style={{ marginLeft: "10px" }}
                                                        value={targetFriendId}
                                                        checked={selectedFriends.includes(targetFriendId)}
                                                        onChange={handleFriendSelect}
                                                    />
                                                </li>
                                            );
                                        })}
                                    </ul>
                                )}
                            </div>
                            <hr></hr>
                            <button className="primary-btn" type="submit" disabled={loading}>Create Chat</button>
                        </form>
                    </div>
                </div>
            }
        </>
    )
}

/** Edit a Chat's details and membership selection. */
export function EditModal ({openModal, setOpenModal, user, chatId, onSaved}) {
    const [chatName, setChatName] = useState("");
    const [query, setQuery] = useState("");
    const [selectedFriends, setSelectedFriends] = useState([]);
    const [chatMembers, setChatMembers] = useState([]);
    const [friends, setFriends] = useState([]);
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(false);

    const csrftoken = getCookie('csrftoken');

    useEffect(() => {
        if (openModal && chatId) {
            /** Load the Chat and eligible friends needed by the edit form. */
            async function loadModalData() {
                const [friendsResponse, membersResponse] = await Promise.all([
                    fetch('/api/friends'),
                    fetch(`/api/members/${chatId}/`),
                ]);
                setFriends(await friendsResponse.json());
                setChatMembers(await membersResponse.json());
            }
            loadModalData();
        }
    }, [openModal, chatId]);

    const filteredFriends = friends.filter(friend => {
        if (!user) return false;
        const friendUsername = friend.user_username !== user.username ? friend.user_username : friend.friend_username;
        return friendUsername.toLowerCase().includes(query.toLowerCase()) && !chatMembers.some(member => member.username === friendUsername);
    });

    /** Add or remove a friend from the edited membership list. */
    const handleFriendSelect = (e) => {
        setSelectedFriends(prev => {
            if (e.target.checked) {
                return [...prev, parseInt(e.target.value)];
            }
            return prev.filter(id => id !== parseInt(e.target.value));
        });
        console.log(selectedFriends);
    }

    /** Persist the edited Chat and newly selected memberships. */
    async function handleSubmit(e) {
        e.preventDefault();
        setError(null);

        if (!chatName.trim() && selectedFriends.length === 0) {
            setError("Enter a new name or select at least one friend.");
            return;
        }
        if (selectedFriends.length > 10) {
            setError("You can only add up to 10 friends to a chat.");
            return;
        }

        setLoading(true);
        try {
            if (chatName.trim().length > 0) {
                const createResponse = await fetch(`/api/chats/${chatId}/`, {
                    method: "PATCH",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": csrftoken,
                    },
                    credentials: "same-origin",
                    body: JSON.stringify({ name: chatName.trim() })
                });

                if (!createResponse.ok) {
                    throw new Error("Failed to create chat");
                }
            }

            if (selectedFriends.length > 0) {
                const addMembersResponse = await fetch(`/api/chats/${chatId}/members`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": csrftoken,
                    },
                    credentials: "same-origin",
                    body: JSON.stringify({ members: selectedFriends }),
                });

                if (!addMembersResponse.ok) {
                    throw new Error("Failed to edit chat members");
                }
            }
            await onSaved?.();
            closeModal();

        } catch (err) {
            console.log(err)
            setError("Failed to edit chat.");
        } finally {
            setLoading(false);
        }
    }

     /** Reset edit state and close the modal. */
     function closeModal() {
        setOpenModal(false);
        setChatName("");
        setQuery("");
        setFriends([]);
        setChatMembers([]);
        setSelectedFriends([]);
    }

    return(
        <>
            {openModal &&
                <div className="modal-overlay" onClick={() => closeModal()}>
                    <div className="modal-content" role="dialog" aria-modal="true" aria-labelledby="edit-chat-title" onClick={(e) => e.stopPropagation()}>
                        <form onSubmit={handleSubmit}>
                            <h2 id="edit-chat-title">Edit Chat</h2>
                            <div>
                                <label htmlFor="chat-name" style={{ display: "block", marginBottom: "10px" }}>Chat Name</label>
                                <input
                                    type="text"
                                    id="chat-name"
                                    placeholder="Edit Chat Name"
                                    value={chatName}
                                    onChange={(e) => setChatName(e.target.value)}
                                />
                            </div>
                            <hr></hr>
                            <div>
                                <label htmlFor="friend-query" style={{ display: "block", marginBottom: "10px" }}>Add up to 10 Friends</label>
                                <input
                                    type="text"
                                    id="friend-query"
                                    placeholder="Search for friends..."
                                    value={query}
                                    onChange={(e) => setQuery(e.target.value)}
                                />
                                {loading && <p>Loading...</p>}
                                {error && <p>{error}</p>}
                                {filteredFriends.length > 0 && (
                                    <ul>
                                        {filteredFriends.map((friend) => {
                                            const targetFriendId = friend.user !== user.id ? friend.user : friend.friend;
                                            const targetUsername = friend.user_username !== user.username ? friend.user_username : friend.friend_username;
                                            return (
                                                <li key={friend.id}>
                                                    <label style={{ display: "inline-block" }} htmlFor={`friend-${friend.id}`}>{targetUsername}</label>
                                                    <input
                                                        type="checkbox"
                                                        id={`friend-${friend.id}`}
                                                        style={{ marginLeft: "10px" }}
                                                        value={targetFriendId}
                                                        checked={selectedFriends.includes(targetFriendId)}
                                                        onChange={handleFriendSelect}
                                                    />
                                                </li>
                                            );
                                        })}
                                    </ul>
                                )}
                            </div>
                            <hr></hr>
                            <button className="primary-btn" type="submit" disabled={loading}>Edit Chat</button>
                        </form>
                    </div>
                </div>
            }
        </>
    )
}
//displays chat messages in a box
/** Render canonical Message projections for the selected Chat. */
export function ChatDisplay({ chatId, messages }) {
    const chatBox = useRef(null);
    useEffect(() => {
        if (chatBox.current) {
            chatBox.current.scrollTop = chatBox.current.scrollHeight;
        }
    }, [messages]);

    if (!chatId) {
        return (
            <section id="chatBox" className="chat-skeleton">
            </section>
        )
    }

    /** Return whether an attachment URL has a supported image extension. */
    const isImage = (url) => {
        const path = url.split(/[?#]/, 1)[0].toLowerCase();
        return /\.(jpg|jpeg|png|gif|webp)$/.test(path);
    }

    return (
        <section id="chatBox">
            {messages.map((message) => (
                <section key={message.id} className='message'>
                    <img src={message.prof_pic} alt={`${message.username}'s profile`} className="user-img"></img>
                    <div className="message-text">
                        <div className='message-header'>
                            <p className='message-username'>{message.username}</p>
                            <p className='message-timestamp'>
                                {(() => {
                                    const dateObj = new Date(message.timestamp);

                                    const dateStr = dateObj.toLocaleDateString('en-US', {
                                        month: 'numeric',
                                        day: 'numeric',
                                        year: 'numeric'
                                    });

                                    const timeStr = dateObj.toLocaleTimeString('en-US', {
                                        hour: 'numeric',
                                        minute: '2-digit',
                                        hour12: true
                                    });

                                    // This joins them with exactly one space (and no comma)
                                    return `${dateStr} ${timeStr}`;
                                })()}
                            </p>
                        </div>
                        <p className='message-msg'>{message.text}</p>
                        {message.attachments && message.attachments.length > 0 && (
                            <div className="message-attachments">
                                {message.attachments.map((attachment) => (
                                    console.log(attachment),
                                    <div key={attachment.id}>
                                        {isImage(attachment.file) ? (
                                            <img src={attachment.file} alt="Attachment" className="message-img"/>
                                        ) : (
                                            <div style={{display: "flex", flexDirection: "row", alignItems: "center"}} className="attachment">
                                                <p style={{marginRight: "10px"}} className="attachment-name">{attachment.name.split("/").pop()}</p>
                                                <a href={attachment.file} download={attachment.name} className="download-button" title="Download">↓</a>
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </section>
            ))}
        </section>
    )
}

//textbox where user types and sends messages
/** Compose text and attachments for the current WebSocket send workflow. */
export function ChatMessageBox({ chatId, send }) {
    const [text, setText] = useState(""); //stores current message in the textbox
    const [attachments, setAttachments] = useState([]);
    const [error, setError] = useState("");
    const [submitting, setSubmitting] = useState(false);

    const csrfToken = getCookie('csrftoken');


    //once user submits a message it trims it and sends over the websocket connection in JSON format
    /** Upload selected files, then send one Message composition. */
    const handleSubmit = async (e) => {
        e.preventDefault()
        if (!chatId || (!text.trim() && attachments.length === 0)) return;

        let fileUrls = []
        setError("");
        setSubmitting(true);

        try {
            if(attachments.length > 0){
                const formData = new FormData();
                attachments.forEach((file) => {
                    formData.append("file", file)
                });

                const response = await fetch('/api/attachments/create/', {
                    method: "POST",
                    headers: {
                        "X-CSRFToken": csrfToken
                    },
                    body: formData
                });

                if (!response.ok) {
                    throw new Error(`Attachment upload failed (${response.status})`);
                }

                const data = await response.json();
                fileUrls = data.attachments
            }

            const sent = send({
                text: text.trim(),
                attachments: fileUrls
            });
            if (sent === false) {
                throw new Error("Chat connection is not ready");
            }

            setText("");
            setAttachments([])
        } catch (err) {
            setError(err.message || "Unable to send message");
        } finally {
            setSubmitting(false);
        }
    };

    /** Submit on Enter while preserving Shift+Enter for new lines. */
    const handleKeyDown = (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSubmit(e);
        }
    }

    /** Resize the composer to fit its text without manual dragging. */
    const handleResize = (e) => {
        const element = e.target;

        element.style.height = "auto";
        const currentScrollHeight = element.scrollHeight;
        const maxHeight = 300;

        if (currentScrollHeight <= maxHeight) {
            element.style.height = `${currentScrollHeight}px`;
            element.style.overflowY = "hidden";
        } else {
            element.style.height = `${maxHeight}px`;
            element.style.overflowY = "auto";
        }

        setText(element.value);
    };

    /** Append images selected by the image input. */
    const handleImageChange = (e) => {
        const file = e.target.files[0]
        if (file) {
            setAttachments(prevAttachments => [...prevAttachments, file]);
        }
    }
    /** Append files selected by the general attachment input. */
    const handleFileChange = (e) => {
        const file = e.target.files[0]
        if (file) {
            setAttachments(prevAttachments => [...prevAttachments, file]);
        }
    }

    /** Remove one pending attachment by its displayed index. */
    const removeAttachment = (index) => {
        setAttachments(prevAttachments => prevAttachments.filter((_, i) => i !== index))
    }

    return (
        <section id="message-box" className={!chatId ? 'disabled' : ''}>
            <form className="message-form" onSubmit={handleSubmit}>
                <div id="attachment-buttons">
                    <label htmlFor="image-input" className="attachment-button" aria-label="Attach image"><FontAwesomeIcon icon={faFileImage} /></label>
                    <input type="file" className="file-input" id="image-input" accept=".png, .jpg, .jpeg" hidden onChange={handleImageChange}></input>
                    <label htmlFor="file-input" className="attachment-button" aria-label="Attach file"><FontAwesomeIcon icon={faFile} /></label>
                    <input type="file" className="file-input" id="file-input" onChange={handleFileChange} hidden></input>
                </div>
                <textarea
                    id="text-box"
                    placeholder={chatId ? 'Type your message here' : 'No chat selected'}
                    disabled={!chatId}
                    aria-label="Message"
                    rows={1}
                    value={text}
                    onChange={(e) => handleResize(e)}
                    onKeyDown={handleKeyDown}
                />
                <button type="submit" className="primary-btn" id="send-btn" disabled={submitting} hidden={!chatId}>Send</button>
            </form>
            {error && <p role="alert">{error}</p>}
            <div id="attachments">
                {attachments.map((file, index) => (
                    <div className="attachment" key={index}>
                        <p>{file.name}</p>
                        <button type="button" aria-label={`Remove ${file.name}`} onClick={() => removeAttachment(index)}><FontAwesomeIcon icon={faTimes} /></button>
                    </div>
                ))}
            </div>
        </section>
    )
}

/** Display current Chat Members and owner-only removal controls. */
export function MembersSidebar({ chatId, user, chatOwner }) {
    const [chatMembers, setChatMembers] = useState([]);
    const [error, setError] = useState("");

    const csrftoken = getCookie('csrftoken');

    useEffect(() => {
        if (chatId) {
            /** Refresh memberships for the selected Chat. */
            async function loadChatMembers() {
                try {
                    const response = await fetch(`/api/members/${chatId}`);
                    if (!response.ok) throw new Error("Failed to load chat members");
                    setChatMembers(await response.json());
                    setError("");
                } catch (err) {
                    setChatMembers([]);
                    setError(err.message);
                }
            }
            loadChatMembers();
        } else {
            setChatMembers([]);
        }
    }, [chatId]);

    /** Remove a confirmed member and refresh membership state. */
    const handleRemoveMember = async (userId, chatId, username) => {
        if (window.confirm(`Are you sure you want to remove ${username} from this chat?`)) {
            try {
                const response = await fetch(`/api/members/${chatId}/${userId}/edit/`, {
                    method: "DELETE",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": csrftoken,
                    },
                    credentials: "same-origin",
                });
                if (!response.ok) throw new Error("Failed to remove member");
                setChatMembers((members) => members.filter((member) => member.user !== userId));
                setError("");
            } catch (err) {
                setError(err.message);
            }
        }
    }

    return (
        <aside className='members-sidebar'>
            <section className='members-section-header'>
                <h2 className='chat-members'>Members</h2>
            </section>
            {error && <p role="alert">{error}</p>}
            {chatMembers.length === 0 ? (
                <p className="no-members">No chat selected</p>
            ) : (
                chatMembers.map((member) => (
                    <section key={member.id} className="member-section">
                        <img src={member.prof_pic} alt={`${member.username}'s profile`}></img>
                        <div className='member-text'>
                            <h3>{member.username}</h3>
                            <sub>Active</sub>
                        </div>
                        {user && chatOwner === user.id && member.user !== user.id && (
                            <button className='primary-btn' onClick={() => handleRemoveMember(member.user, chatId, member.username)}>
                                Kick
                            </button>
                        )}
                    </section>
                ))
            )}
        </aside>
    );
}
const rootElement = document.getElementById('root');
if (rootElement) {
    createRoot(rootElement).render(<ChatPage />);
}
