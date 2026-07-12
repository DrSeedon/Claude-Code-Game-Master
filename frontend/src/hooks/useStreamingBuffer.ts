import { useRef, useState, useCallback, useEffect } from 'react';

const BASE_CPS = 12;          // min chars per frame  (Orchestra _STREAM_BASE_CPS)
const PARSE_INTERVAL = 50;    // ms between visible updates (Orchestra _STREAM_PARSE_INTERVAL)

export function useStreamingBuffer() {
  const pending = useRef('');        // raw deltas not yet shown  (streamPending)
  const shown   = useRef('');        // chars already drawn       (streamContent)
  const raf      = useRef<number | null>(null);
  const lastParse= useRef(0);
  const [display, setDisplay] = useState('');   // what react-markdown renders
  const [active, setActive]   = useState(false);

  const tick = useCallback(() => {
    raf.current = null;
    if (!pending.current) return;
    // adaptive chunk: catch up if buffer is large   (Orchestra Math.floor(len/8))
    const size = Math.max(BASE_CPS, Math.floor(pending.current.length / 8));
    shown.current += pending.current.slice(0, size);
    pending.current = pending.current.slice(size);
    const now = performance.now();
    if (now - lastParse.current >= PARSE_INTERVAL || !pending.current) {
      lastParse.current = now;
      setDisplay(shown.current);          // <-- the ONLY setState in the loop, ≤20/s
    }
    if (pending.current) raf.current = requestAnimationFrame(tick);
  }, []);

  const push = useCallback((delta: string) => {   // called on every `stream` event
    setActive(true);
    pending.current += delta;
    if (raf.current == null) raf.current = requestAnimationFrame(tick);
  }, [tick]);

  const finalize = useCallback((final?: string) => {   // called on `text`
    if (raf.current != null) { cancelAnimationFrame(raf.current); raf.current = null; }
    const text = final ?? (shown.current + pending.current);
    pending.current = ''; shown.current = ''; lastParse.current = 0;
    setDisplay(''); setActive(false);
    return text;    // caller pushes this into messageHistory as a finalized message
  }, []);

  const reset = useCallback(() => {   // on reconnect / campaign switch
    if (raf.current != null) cancelAnimationFrame(raf.current);
    raf.current = null; pending.current = ''; shown.current = '';
    setDisplay(''); setActive(false);
  }, []);

  useEffect(() => () => { if (raf.current != null) cancelAnimationFrame(raf.current); }, []);
  return { display, active, push, finalize, reset };
}
