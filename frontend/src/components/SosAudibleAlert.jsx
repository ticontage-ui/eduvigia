import React, { useCallback, useEffect, useRef, useState } from "react";
import { Siren, Volume2, VolumeX } from "lucide-react";
import { api } from "../services/api";

const ALARM_STATUSES = new Set(["ACTIVE", "CANCEL_REQUESTED"]);
const POLL_MS = 3000;
const REPEAT_MS = 12000;
const MUTE_MS = 60000;

export default function SosAudibleAlert({ enabled = false, onFeedback = () => {} }) {
  const audioContextRef = useRef(null);
  const toneRef = useRef(null);
  const previousCountsRef = useRef(new Map());
  const alarmRowsRef = useRef([]);
  const mutedUntilRef = useRef(0);
  const repeatTimerRef = useRef(null);
  const [audioReady, setAudioReady] = useState(false);
  const [alarmRows, setAlarmRows] = useState([]);
  const [mutedUntil, setMutedUntil] = useState(0);
  const [pollError, setPollError] = useState("");

  const stopTone = useCallback(() => {
    const current = toneRef.current;
    toneRef.current = null;
    if (!current) return;
    (current.oscillators || []).forEach((oscillator) => {
      try { oscillator.stop(); } catch {}
      try { oscillator.disconnect(); } catch {}
    });
    try { current.gain?.disconnect(); } catch {}
  }, []);

  const playSirenBurst = useCallback(() => {
    const context = audioContextRef.current;
    if (!enabled || !context || context.state !== "running") return;
    if (mutedUntilRef.current > Date.now()) return;
    if (!alarmRowsRef.current.length) return;

    stopTone();

    const now = context.currentTime;
    const duration = 2.6;
    const gain = context.createGain();
    const primary = context.createOscillator();
    const secondary = context.createOscillator();

    primary.type = "sawtooth";
    secondary.type = "square";

    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(0.075, now + 0.04);

    for (let index = 0; index < 7; index += 1) {
      const time = now + (index * 0.36);
      const high = index % 2 === 0;
      primary.frequency.setValueAtTime(high ? 980 : 690, time);
      secondary.frequency.setValueAtTime(high ? 490 : 345, time);
    }

    gain.gain.setValueAtTime(0.075, now + duration - 0.12);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + duration);

    primary.connect(gain);
    secondary.connect(gain);
    gain.connect(context.destination);

    primary.start(now);
    secondary.start(now);
    primary.stop(now + duration);
    secondary.stop(now + duration);

    toneRef.current = { oscillators: [primary, secondary], gain };

    primary.onended = () => {
      if (toneRef.current?.oscillators?.[0] === primary) {
        try { gain.disconnect(); } catch {}
        toneRef.current = null;
      }
    };
  }, [enabled, stopTone]);

  const armAudio = useCallback(async () => {
    if (!enabled) return false;
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) {
      setPollError("Este navegador não oferece Web Audio para o alerta de emergência.");
      return false;
    }

    try {
      let context = audioContextRef.current;
      if (!context || context.state === "closed") {
        context = new AudioContextClass();
        audioContextRef.current = context;
      }
      if (context.state === "suspended") {
        await context.resume();
      }
      const ready = context.state === "running";
      setAudioReady(ready);

      if (ready && alarmRowsRef.current.length && mutedUntilRef.current <= Date.now()) {
        window.setTimeout(playSirenBurst, 30);
      }
      return ready;
    } catch (error) {
      setPollError(error?.message || "O navegador bloqueou o áudio de emergência.");
      return false;
    }
  }, [enabled, playSirenBurst]);

  const poll = useCallback(async () => {
    if (!enabled) return;
    try {
      const list = await api("/sos");
      const rows = Array.isArray(list) ? list : [];
      const alarmRowsNext = rows.filter((row) => ALARM_STATUSES.has(String(row.status || "").toUpperCase()));
      const previous = previousCountsRef.current;
      let newOrReinforced = false;

      for (const row of alarmRowsNext) {
        const count = Number(row.repeat_count || 1);
        const previousCount = previous.get(row.id);
        if (previousCount === undefined || count > previousCount) {
          newOrReinforced = true;
        }
      }

      previousCountsRef.current = new Map(
        rows.map((row) => [row.id, Number(row.repeat_count || 1)])
      );
      alarmRowsRef.current = alarmRowsNext;
      setAlarmRows(alarmRowsNext);
      setPollError("");

      if (!alarmRowsNext.length) {
        stopTone();
      } else if (
        newOrReinforced &&
        audioContextRef.current?.state === "running" &&
        mutedUntilRef.current <= Date.now()
      ) {
        playSirenBurst();
      }
    } catch (error) {
      setPollError(error?.message || "Falha ao consultar SOS para alerta sonoro.");
    }
  }, [enabled, playSirenBurst, stopTone]);

  useEffect(() => {
    if (!enabled) {
      alarmRowsRef.current = [];
      setAlarmRows([]);
      stopTone();
      return undefined;
    }

    poll();
    const timer = window.setInterval(poll, POLL_MS);
    const onFocus = () => poll();
    window.addEventListener("focus", onFocus);

    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", onFocus);
    };
  }, [enabled, poll, stopTone]);

  useEffect(() => {
    if (!enabled || audioReady) return undefined;
    const unlock = () => { armAudio(); };
    window.addEventListener("pointerdown", unlock, { passive: true });
    window.addEventListener("keydown", unlock);
    return () => {
      window.removeEventListener("pointerdown", unlock);
      window.removeEventListener("keydown", unlock);
    };
  }, [enabled, audioReady, armAudio]);

  useEffect(() => {
    if (repeatTimerRef.current) {
      window.clearInterval(repeatTimerRef.current);
      repeatTimerRef.current = null;
    }

    if (
      enabled &&
      audioReady &&
      alarmRows.length > 0 &&
      mutedUntilRef.current <= Date.now()
    ) {
      repeatTimerRef.current = window.setInterval(playSirenBurst, REPEAT_MS);
    } else {
      stopTone();
    }

    return () => {
      if (repeatTimerRef.current) {
        window.clearInterval(repeatTimerRef.current);
        repeatTimerRef.current = null;
      }
    };
  }, [enabled, audioReady, alarmRows.length, mutedUntil, playSirenBurst, stopTone]);

  useEffect(() => {
    if (!mutedUntil) return undefined;
    const wait = Math.max(0, mutedUntil - Date.now());
    const timer = window.setTimeout(() => {
      mutedUntilRef.current = 0;
      setMutedUntil(0);
      if (alarmRowsRef.current.length && audioContextRef.current?.state === "running") {
        playSirenBurst();
      }
    }, wait + 25);
    return () => window.clearTimeout(timer);
  }, [mutedUntil, playSirenBurst]);

  useEffect(() => () => {
    stopTone();
    if (repeatTimerRef.current) window.clearInterval(repeatTimerRef.current);
    const context = audioContextRef.current;
    if (context && context.state !== "closed") {
      context.close().catch(() => null);
    }
  }, [stopTone]);

  if (!enabled) return null;

  const isMuted = mutedUntil > Date.now();
  const activeCount = alarmRows.length;
  const primarySchool = alarmRows[0]?.school_name || "";
  const reinforced = alarmRows.some((row) => Number(row.repeat_count || 1) > 1);

  const handleControl = async () => {
    if (!audioReady) {
      const ready = await armAudio();
      if (ready) {
        onFeedback(
          "success",
          "Som de emergência ativado",
          "A Central está habilitada para receber alertas sonoros de SOS."
        );
      }
      return;
    }

    if (!activeCount) return;

    if (isMuted) {
      mutedUntilRef.current = 0;
      setMutedUntil(0);
      onFeedback("success", "Alerta sonoro reativado", "O SOS volta a emitir o aviso sonoro.");
      window.setTimeout(playSirenBurst, 25);
      return;
    }

    const until = Date.now() + MUTE_MS;
    mutedUntilRef.current = until;
    setMutedUntil(until);
    stopTone();
    onFeedback(
      "warning",
      "Alerta sonoro silenciado por 60 segundos",
      "O SOS permanece ativo e visível. O estado operacional não foi alterado."
    );
  };

  let label = "Alertas sonoros ativos";
  let detail = "Central pronta para novos SOS";
  if (!audioReady) {
    label = activeCount ? `SOS ATIVO (${activeCount})` : "Ativar som de emergência";
    detail = activeCount ? "Clique para liberar o áudio do navegador" : "Áudio ainda não liberado pelo navegador";
  } else if (activeCount && isMuted) {
    label = `SOS ATIVO (${activeCount}) · SILENCIADO`;
    detail = "Silêncio temporário; o evento continua aberto";
  } else if (activeCount) {
    label = `SOS ATIVO (${activeCount}) · SOM ATIVO`;
    detail = reinforced
      ? `${primarySchool} · houve reforço do acionamento`
      : primarySchool;
  }

  return (
    <div
      className={`sosAudioControl ${activeCount ? "critical" : "ready"} ${isMuted ? "muted" : ""}`}
      title={pollError || detail}
      role={activeCount ? "alert" : "status"}
      aria-live={activeCount ? "assertive" : "polite"}
    >
      <Siren size={18} className={activeCount && !isMuted ? "sosAudioPulse" : ""} />
      <div className="sosAudioCopy">
        <strong>{label}</strong>
        <span>{pollError || detail}</span>
      </div>
      <button
        type="button"
        className="sosAudioButton"
        onClick={handleControl}
        disabled={audioReady && !activeCount}
      >
        {!audioReady ? (
          <><Volume2 size={15} /> Ativar</>
        ) : isMuted ? (
          <><Volume2 size={15} /> Reativar</>
        ) : activeCount ? (
          <><VolumeX size={15} /> Silenciar 60s</>
        ) : (
          <><Volume2 size={15} /> Ativo</>
        )}
      </button>
    </div>
  );
}