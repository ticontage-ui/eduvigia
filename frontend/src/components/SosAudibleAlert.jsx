import React, { useCallback, useEffect, useRef, useState } from "react";
import { Siren, Volume2, VolumeX } from "lucide-react";
import { api } from "../services/api";

const ALARM_STATUSES = new Set(["ACTIVE", "CANCEL_REQUESTED"]);
const POLL_MS = 3000;
const REPEAT_MS = 12000;
const MUTE_MS = 60000;
const SOS_AUDIO_URL = "/audio/nextalk-sos.mp3";

export default function SosAudibleAlert({ enabled = false, onFeedback = () => {} }) {
  const audioContextRef = useRef(null);
  const audioBufferRef = useRef(null);
  const activeSourceRef = useRef(null);
  const loadingAudioRef = useRef(null);
  const previousCountsRef = useRef(new Map());
  const alarmRowsRef = useRef([]);
  const mutedUntilRef = useRef(0);
  const repeatTimerRef = useRef(null);

  const [audioReady, setAudioReady] = useState(false);
  const [alarmRows, setAlarmRows] = useState([]);
  const [mutedUntil, setMutedUntil] = useState(0);
  const [pollError, setPollError] = useState("");

  const stopAudio = useCallback(() => {
    const source = activeSourceRef.current;
    activeSourceRef.current = null;
    if (!source) return;
    try { source.stop(); } catch {}
    try { source.disconnect(); } catch {}
  }, []);

  const ensureAudioContext = useCallback(async () => {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) {
      throw new Error("Este navegador não oferece Web Audio para o alerta de emergência.");
    }

    let context = audioContextRef.current;
    if (!context || context.state === "closed") {
      context = new AudioContextClass();
      audioContextRef.current = context;
    }

    if (context.state === "suspended") {
      await context.resume();
    }

    if (context.state !== "running") {
      throw new Error("O navegador ainda não liberou o áudio de emergência.");
    }

    return context;
  }, []);

  const ensureOfficialAudioBuffer = useCallback(async () => {
    if (audioBufferRef.current) return audioBufferRef.current;
    if (loadingAudioRef.current) return loadingAudioRef.current;

    loadingAudioRef.current = (async () => {
      const context = await ensureAudioContext();
      const response = await fetch(SOS_AUDIO_URL, { cache: "no-store" });
      if (!response.ok) {
        throw new Error(`Falha ao carregar a sirene oficial de SOS (${response.status}).`);
      }

      const bytes = await response.arrayBuffer();
      const decoded = await context.decodeAudioData(bytes.slice(0));
      audioBufferRef.current = decoded;
      return decoded;
    })();

    try {
      return await loadingAudioRef.current;
    } finally {
      loadingAudioRef.current = null;
    }
  }, [ensureAudioContext]);

  const playSosAlert = useCallback(async () => {
    if (!enabled) return false;
    if (mutedUntilRef.current > Date.now()) return false;
    if (!alarmRowsRef.current.length) return false;

    try {
      const context = await ensureAudioContext();
      const buffer = await ensureOfficialAudioBuffer();

      stopAudio();

      const source = context.createBufferSource();
      source.buffer = buffer;
      source.connect(context.destination);
      source.onended = () => {
        if (activeSourceRef.current === source) {
          activeSourceRef.current = null;
        }
        try { source.disconnect(); } catch {}
      };

      activeSourceRef.current = source;
      source.start(0);

      setAudioReady(true);
      setPollError("");
      return true;
    } catch (error) {
      setAudioReady(false);
      setPollError(
        error?.message ||
          "O navegador bloqueou a sirene oficial de emergência. Clique em Ativar."
      );
      return false;
    }
  }, [enabled, ensureAudioContext, ensureOfficialAudioBuffer, stopAudio]);

  const armAudio = useCallback(async () => {
    if (!enabled) return false;

    try {
      await ensureAudioContext();
      await ensureOfficialAudioBuffer();
      setAudioReady(true);
      setPollError("");

      if (alarmRowsRef.current.length && mutedUntilRef.current <= Date.now()) {
        window.setTimeout(() => { playSosAlert(); }, 25);
      }
      return true;
    } catch (error) {
      setAudioReady(false);
      setPollError(error?.message || "O navegador bloqueou o áudio de emergência.");
      return false;
    }
  }, [enabled, ensureAudioContext, ensureOfficialAudioBuffer, playSosAlert]);

  const poll = useCallback(async () => {
    if (!enabled) return;

    try {
      const list = await api("/sos");
      const rows = Array.isArray(list) ? list : [];
      const alarmRowsNext = rows.filter((row) =>
        ALARM_STATUSES.has(String(row.status || "").toUpperCase())
      );

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
        stopAudio();
      } else if (
        newOrReinforced &&
        audioReady &&
        mutedUntilRef.current <= Date.now()
      ) {
        playSosAlert();
      }
    } catch (error) {
      setPollError(error?.message || "Falha ao consultar SOS para alerta sonoro.");
    }
  }, [enabled, audioReady, playSosAlert, stopAudio]);

  useEffect(() => {
    if (!enabled) {
      alarmRowsRef.current = [];
      setAlarmRows([]);
      stopAudio();
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
  }, [enabled, poll, stopAudio]);

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
      repeatTimerRef.current = window.setInterval(() => {
        playSosAlert();
      }, REPEAT_MS);
    } else {
      stopAudio();
    }

    return () => {
      if (repeatTimerRef.current) {
        window.clearInterval(repeatTimerRef.current);
        repeatTimerRef.current = null;
      }
    };
  }, [enabled, audioReady, alarmRows.length, mutedUntil, playSosAlert, stopAudio]);

  useEffect(() => {
    if (!mutedUntil) return undefined;

    const wait = Math.max(0, mutedUntil - Date.now());
    const timer = window.setTimeout(() => {
      mutedUntilRef.current = 0;
      setMutedUntil(0);

      if (
        alarmRowsRef.current.length &&
        audioContextRef.current?.state === "running"
      ) {
        playSosAlert();
      }
    }, wait + 25);

    return () => window.clearTimeout(timer);
  }, [mutedUntil, playSosAlert]);

  useEffect(() => () => {
    stopAudio();

    if (repeatTimerRef.current) {
      window.clearInterval(repeatTimerRef.current);
    }

    const context = audioContextRef.current;
    if (context && context.state !== "closed") {
      context.close().catch(() => null);
    }
  }, [stopAudio]);

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
          "Sirene oficial de SOS ativada",
          "A Central está habilitada para receber o alerta sonoro oficial do NexTalk."
        );
      }
      return;
    }

    if (!activeCount) return;

    if (isMuted) {
      mutedUntilRef.current = 0;
      setMutedUntil(0);
      onFeedback(
        "success",
        "Alerta sonoro reativado",
        "O SOS volta a emitir a sirene oficial de emergência."
      );
      window.setTimeout(() => { playSosAlert(); }, 25);
      return;
    }

    const until = Date.now() + MUTE_MS;
    mutedUntilRef.current = until;
    setMutedUntil(until);
    stopAudio();

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
    detail = activeCount
      ? "Clique para liberar a sirene oficial do navegador"
      : "Sirene oficial ainda não liberada pelo navegador";
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