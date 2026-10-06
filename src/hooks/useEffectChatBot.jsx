

import { useState, useEffect, useRef} from 'react';
import { checkSession, getChats } from '../services/chatbot.service';

function useEffectChatBot() {

    const [chats, setChats] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const endOfMessagesRef = useRef(null);

    useEffect(() => {
        const controller = new AbortController();

        const loadHistory = async () => {
            try {
                const session = await checkSession();
                if (controller.signal.aborted) return;

                if (session?.authenticated) {
                    const history = await getChats({ signal: controller.signal });
                    if (!controller.signal.aborted) setChats(Array.isArray(history) ? history : []);
                }
            } catch (err) {
                if (!controller.signal.aborted) setError(err);
            } finally {
                if (!controller.signal.aborted) setLoading(false);
            }
        };

        loadHistory();
        return () => controller.abort();
    }, []);


    // useEffect(() => {
    //     endOfMessagesRef.current?.scrollIntoView({ behavior: "smooth" });
    // }, [chats]);

    return {chats, loading, error, endOfMessagesRef}

}

export default useEffectChatBot;
