import { createRoot } from 'react-dom/client';
import { useState, useEffect, useRef, useCallback } from 'react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faCircleXmark } from '@fortawesome/free-solid-svg-icons';
import { faCircleCheck } from '@fortawesome/free-solid-svg-icons';
import { faEllipsisVertical } from '@fortawesome/free-solid-svg-icons';
const root = createRoot(document.getElementById('root'));

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

/** Load the current user and coordinate the friends page sections. */
function FriendPage(){
    const [user, setUser] = useState(null); // holds the current user thats logged in
    const [friends, setFriends] = useState([]);

    /** Refresh friendships after a request changes their state. */
    const refreshFriends = async () => {
        const response = await fetch("http://127.0.0.1:8000/api/friends");
        const data = await response.json();
        setFriends(data);
    };

    //calls backend api to get and store current user
    useEffect(() => {
        /** Load the authenticated user's browser-facing profile. */
        async function loadUser() {
            const response = await fetch(`http://127.0.0.1:8000/api/me`);
            const data = await response.json();
            setUser(data);
        }
        loadUser();
        refreshFriends();
    }, []);

    return(
        <>
            <SearchBar />
            <FriendRequest refreshFriends={refreshFriends} />
            <Friends user={user} friends={friends} />
        </>
    )
}

/** Search for users and send new friend requests. */
function SearchBar(){
    const [query, setQuery] = useState("");
    const [results, setResults] = useState([]);
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(false);

    const csrftoken = getCookie('csrftoken');

    useEffect(() => {
        if (query.trim().length === 0) {
            setResults([]);
            setError(null);
            return;
        }
        const timeout = setTimeout( async () => {
            setLoading(true);
            setError(null);

            try{
                const response = await fetch(`http://127.0.0.1:8000/api/search_users/${query}`);
                const data = await response.json();
                setResults(data);
            } catch (err) {
                setError("Failed to search users.");
            } finally {
                setLoading(false);
            }
        }, 400); // Debounce the search by 400ms

        return () => clearTimeout(timeout);

    }, [query]);

    /** Send a pending friend request to the selected user. */
    const handleSubmit = async(receiverId) =>{
        try{
            fetch(`http://127.0.0.1:8000/api/friend_requests/create`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrftoken,
                },
                credentials: "same-origin",
                body: JSON.stringify({ receiver : receiverId })
            });
        } catch (err) {
            setError("Failed to send friend request.");
        }
    }

    return(
        <section id="search-bar">
            <h1 className="title">Search Friends</h1>
            <input
                type="text"
                placeholder="Search for new friends..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="friend-search"
            />
            {loading && <p>Loading...</p>}
            {error && <p>{error}</p>}
            {results.length > 0 && (
                <ul>
                    {results.slice(0, 10).map((user) => (
                        <li key={user.id}>
                            <img src={user.prof_pic} />
                            <h3>{user.username}</h3>
                            <button onClick={() => handleSubmit(user.id)}>Add Friend</button>
                        </li>
                    ))}
                </ul>
            )}
        </section>
    )
}

/** Display incoming requests and handle acceptance or rejection. */
function FriendRequest({ refreshFriends }){
    const [ friendRequests, setFriendRequests] = useState([]);
    const [ error, setError] = useState(null);

    const csrftoken = getCookie('csrftoken');

    useEffect(() => {
        /** Load friend requests addressed to the current user. */
        async function loadFriendRequests(){
            const response = await fetch("http://127.0.0.1:8000/api/friend_requests");
            const data = await response.json();
            setFriendRequests(data);
        }
        loadFriendRequests();
    }, [])

    /** Accept a request, create the friendship, and refresh the page. */
    const handleAcceptRequest = async(requestID, senderID) => {
        try{
             await fetch(`http://127.0.0.1:8000/api/friend_requests/${senderID}/update`, {
                method: "PATCH",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrftoken,
                },
                credentials: "same-origin",
                body: JSON.stringify({ status: "Accepted" })
            });

            await fetch(`http://127.0.0.1:8000/api/friend/create`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrftoken,
                },
                credentials: "same-origin",
                body: JSON.stringify({ friend : senderID })
            });

            setFriendRequests((prev) =>
                prev.filter((request) => request.id !== requestID)
            );
            await refreshFriends();

        } catch (err) {
            setError("Failed to accept friend request.");
        }
    }

    /** Reject a pending friend request. */
    const handleDeclineRequest = async(requestID, senderID) => {
        try{
             await fetch(`http://127.0.0.1:8000/api/friend_requests/${senderID}/update`, {
                method: "PATCH",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrftoken,
                },
                credentials: "same-origin",
                body: JSON.stringify({ status: "Rejected" })
            });

            setFriendRequests((prev) =>
                prev.filter((request) => request.id !== requestID)
            );

        } catch (err) {
            setError("Failed to reject friend request.");
        }
    }
    return(
        <>
            <section id="friend-requests">
                <h1 className="title">Friend Requests</h1>
                {friendRequests.filter((request) => (request.status == "Pending")).map((request) => (
                    <section className="request" key={request.id}>
                        <h3>{request.sender_username}</h3>
                        <FontAwesomeIcon icon={faCircleCheck} style={{color: "rgb(8, 138, 98)",}} onClick={() => handleAcceptRequest(request.id, request.sender)} />
                        <FontAwesomeIcon icon={faCircleXmark} style={{color: "rgb(199, 22, 22)",}} onClick={() => handleDeclineRequest(request.id, request.sender)} />
                    </section>
                ))}
            </section>
        </>
    )
}

/** Render the current user's friendship list. */
function Friends( {user, friends} ){
    return(
        <>
            <section id="friends">
                <h1 className="title">Friends</h1>
                {friends.map((friend) => (
                    <section className="friend" key={friend.id}>
                        {
                            friend.user_username != user.username? 
                            <h3 className="friend-name">{friend.user_username}</h3>:
                            <h3 className="friend-name">{friend.friend_username}</h3>
                        }
                        <FontAwesomeIcon icon={faEllipsisVertical} className="dropdown-icon" style={{color: "rgb(8, 138, 98)",}} />
                    </section> 
                ))}
            </section>
        </>
    )
}

root.render(
    <FriendPage />
)
