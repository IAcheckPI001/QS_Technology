// Nhập bằng giọng nói qua Web Speech API của trình duyệt (WU-17 đợt 3A; không cần backend, không thêm thư viện).
// Chữ nhận được đổ vào ô nhập để khách xem/sửa rồi mới gửi; không tự gửi. Trình duyệt không hỗ trợ
// (Firefox, iOS cũ) → `supported=false`, giao diện ẩn nút. Lưu ý: Chrome gửi âm thanh lên máy chủ của Google để nhận dạng.

import { useCallback, useEffect, useRef, useState } from 'react';

const Recognition = typeof window !== 'undefined' ? window.SpeechRecognition || window.webkitSpeechRecognition : undefined;

export function useSpeechInput({ lang = 'vi-VN', onText } = {}) {
    const [listening, setListening] = useState(false);
    const [error, setError] = useState('');
    const recognitionRef = useRef(null);
    const onTextRef = useRef(onText);
    useEffect(() => {
        onTextRef.current = onText;
    }, [onText]);

    const stop = useCallback(() => {
        recognitionRef.current?.stop();
    }, []);

    const start = useCallback((baseText = '') => {
        if (!Recognition || recognitionRef.current) return;
        const recognition = new Recognition();
        recognition.lang = lang;
        recognition.interimResults = true;
        recognition.continuous = false;
        recognition.maxAlternatives = 1;
        const prefix = baseText.trim() ? `${baseText.trim()} ` : '';
        recognition.onresult = (event) => {
            let transcript = '';
            for (let i = 0; i < event.results.length; i += 1) transcript += event.results[i][0].transcript;
            onTextRef.current?.(prefix + transcript.trim());
        };
        recognition.onerror = (event) => {
            // not-allowed: khách chặn micro; no-speech: không nghe thấy gì; aborted: tự dừng.
            if (event.error !== 'aborted') setError(event.error || 'unknown');
        };
        recognition.onend = () => {
            recognitionRef.current = null;
            setListening(false);
        };
        recognitionRef.current = recognition;
        setError('');
        setListening(true);
        try {
            recognition.start();
        } catch {
            recognitionRef.current = null;
            setListening(false);
            setError('start_failed');
        }
    }, [lang]);

    useEffect(() => () => recognitionRef.current?.abort(), []);

    return { supported: Boolean(Recognition), listening, error, start, stop, clearError: () => setError('') };
}
