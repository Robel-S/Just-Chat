import { createRoot } from 'react-dom/client';
import { useState, useEffect, useRef, useCallback } from 'react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faCircleXmark } from '@fortawesome/free-solid-svg-icons';
import { faCircleCheck } from '@fortawesome/free-solid-svg-icons';

const root = createRoot(document.getElementById('root'));

function FriendPage(){
    const [user, setUser] = useState(null); //holds the current user thats logged in
     
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
            <FriendRequest />
            <Friends user={user} />
        </>
    )
}

function FriendRequest(){
    const [ friendRequests, setFriendRequests] = useState([]);

    useEffect(() => {
        async function loadFriendRequests(){
            const response = await fetch("http://127.0.0.1:8000/api/friend_requests");
            const data = await response.json();
            setFriendRequests(data);
        }
        loadFriendRequests();
    }, [])

    return(
        <>
            <section id="friend-requests">
                <h2>Friend Requests</h2>
                {friendRequests.filter((request) => (request.status == "Pending")).map((request) => (
                    <section className="request" key={request.id}>
                        <h3>{request.sender_username}</h3>
                        <FontAwesomeIcon icon={faCircleCheck} style={{color: "rgb(8, 138, 98)",}} />
                        <FontAwesomeIcon icon={faCircleXmark} style={{color: "rgb(199, 22, 22)",}} />
                    </section>
                ))}
            </section>
        </>
    )
}

function Friends( {user} ){
    const [friends, setFriends] = useState([]);

    useEffect(() => {
        async function loadFriends(){
            const response = await fetch("http://127.0.0.1:8000/api/friends");
            const data = await response.json();
            setFriends(data);
        }
        loadFriends()
    }, [])

    return(
        <>
            <section id="friends">
                <h2>Friends</h2>
                {friends.map((friend) => (
                    <section className="friend" key={friend.id}>
                        {
                            friend.user_username != user.username? 
                            <h3>{friend.user_username}</h3>: 
                            <h3>{friend.friend_username}</h3>
                        }
                    </section> 
                ))}
            </section>
        </>
    )
}

root.render(
    <FriendPage />
)