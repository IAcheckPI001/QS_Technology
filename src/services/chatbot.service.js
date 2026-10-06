

import {apiFetch} from './api.service.js'


export const getChats = async (config = {}) => {
    const res = await apiFetch.get("/chats", config);
    return res.data;
};

export class ChatStreamError extends Error {
    constructor(message, code = 'chat_stream_error') {
        super(message);
        this.name = 'ChatStreamError';
        this.code = code;
    }
}

// POST requires fetch (EventSource only supports GET). The backend uses SSE framing.
export const streamChatbotResponse = async (message, { signal, onChunk } = {}) => {
    const baseURL = (apiFetch.defaults.baseURL || '').replace(/\/$/, '');
    const response = await fetch(`${baseURL}/chatbot`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
        body: JSON.stringify({ message }),
        signal,
    });

    if (!response.ok) {
        let details = `Chat request failed (${response.status})`;
        try {
            const payload = await response.json();
            details = payload.detail?.message || payload.detail || payload.message || details;
            if (typeof details !== 'string') details = `Chat request failed (${response.status})`;
        } catch { /* non-JSON proxy errors use the status fallback */ }
        throw new ChatStreamError(details, `http_${response.status}`);
    }

    if (!response.body) {
        throw new Error('The chat service did not return a readable response stream.');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let eventName = 'message';
    let eventData = [];
    let receivedDone = false;

    const dispatchEvent = () => {
        if (eventData.length === 0) {
            eventName = 'message';
            return;
        }
        const rawData = eventData.join('\n');
        try {
            const payload = JSON.parse(rawData);
            if (eventName === 'delta' && typeof payload.text === 'string') onChunk?.(payload.text);
            if (eventName === 'done') receivedDone = true;
            if (eventName === 'error') throw new ChatStreamError(payload.message || 'Chat service failed.', payload.code);
        } catch (error) {
            if (error instanceof ChatStreamError) throw error;
            throw new ChatStreamError('The chat service returned an invalid stream event.', 'invalid_stream_event');
        } finally {
            eventName = 'message';
            eventData = [];
        }
    };

    const consumeLine = (line) => {
        if (line === '') return dispatchEvent();
        if (line.startsWith(':')) return; // SSE heartbeat
        const separator = line.indexOf(':');
        const field = separator < 0 ? line : line.slice(0, separator);
        const value = separator < 0 ? '' : line.slice(separator + 1).replace(/^ /, '');
        if (field === 'event') eventName = value;
        if (field === 'data') eventData.push(value);
    };

    try {
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            let newline;
            while ((newline = buffer.indexOf('\n')) !== -1) {
                let line = buffer.slice(0, newline);
                buffer = buffer.slice(newline + 1);
                if (line.endsWith('\r')) line = line.slice(0, -1);
                consumeLine(line);
            }
        }

        buffer += decoder.decode();
        if (buffer) consumeLine(buffer.replace(/\r$/, ''));
        dispatchEvent();
        if (!receivedDone) throw new ChatStreamError('The chat stream ended before completion.', 'incomplete_stream');
    } finally {
        reader.releaseLock();
    }
};

export const checkSession = async () => {
  const res = await apiFetch.get("/check-session");
  return res.data;
};

export const checkAccount = async (user_key, passkey) =>{
    const res = await apiFetch.post("/check_account", { user_key, passkey });
    return res.data;
}

export const logout = async () =>{
    const res = await apiFetch.get("/logout");
    return res.data;
}

export const getBlogs = () => {
    return apiFetch.get("/blogs");
};

export const getBlogsUser = () => {
    return apiFetch.get("/manage_blogs");
};

export const getTags = () => {
    return apiFetch.get("/get_tags");
};

export const getTagsUser = () => {
    return apiFetch.get("/get_tags_user");
};

export const getListNickname = () => {
    return apiFetch.get("/get_nickname");
};

