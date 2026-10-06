

import axios from "axios"
const API_URL = import.meta.env.VITE_API_URL || (import.meta.env.DEV ? 'http://localhost:8000' : '');


export const apiFetch = axios.create({
    baseURL : API_URL,
    headers: {
        "Content-Type": "application/json"
    },
    withCredentials: true,
});

