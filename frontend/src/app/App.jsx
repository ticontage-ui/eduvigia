import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Bell,
  Building2,
  Camera,
  CheckCircle2,
  ChevronDown,
  CircleUserRound,
  ClipboardList,
  Eye,
  Headphones,
  History,
  FileVideo,
  Fingerprint,
  Mail,
  Phone,
  MapPinned,
  Crosshair,
  LayoutDashboard,
  Menu,
  MoreHorizontal,
  Download,
  FileImage,
  Maximize2,
  RefreshCw,
  Wrench,
  Plus,
  Search,
  Server,
  Settings,
  ShieldCheck,
  Siren,
  Trash2,
  Truck,
  Users,
  Video,
  XCircle,
} from "lucide-react";
import "../styles/main.css";

import { API_URL } from "../config/runtime";
import { api } from "../services/api";

const CameraFleetStatusContext = React.createContext({
  total: 0,
  online: 0,
  offline: 0,
  attention: 0,
  tone: "neutral",
  label: "SEM CÂMERAS",
  detail: "Nenhuma câmera cadastrada para compor o estado operacional.",
});

function deriveCameraFleetStatus(cameras = []) {
  const total = cameras.length;
  const normalized = cameras.map((camera) => String(camera?.status || "").toUpperCase());
  const online = normalized.filter((status) => status === "ONLINE").length;
  const offline = normalized.filter((status) => status === "OFFLINE").length;
  const attention = total - online - offline;

  if (total === 0) {
    return {
      total, online, offline, attention,
      tone: "neutral",
      label: "SEM CÂMERAS",
      detail: "Nenhuma câmera cadastrada para compor o estado operacional.",
    };
  }

  if (online === total) {
    return {
      total, online, offline, attention,
      tone: "success",
      label: "SISTEMA ONLINE",
      detail: `${online}/${total} câmeras online.`,
    };
  }

  if (offline === total) {
    return {
      total, online, offline, attention,
      tone: "danger",
      label: "SISTEMA OFFLINE",
      detail: `${offline}/${total} câmeras offline.`,
    };
  }

  const hasOnlineAndOffline = online > 0 && offline > 0;
  return {
    total, online, offline, attention,
    tone: "warning",
    label: hasOnlineAndOffline ? "SISTEMA PARCIAL" : "SISTEMA COM ATENÇÃO",
    detail: `${online} online · ${offline} offline${attention ? ` · ${attention} em atenção` : ""}.`,
  };
}

function useCameraFleetStatus() {
  return React.useContext(CameraFleetStatusContext);
}

function SecureStreamFrame({ cameraId = null, profile = "SUB", testStream = false, title = "Vídeo EduVigIA" }) {
  const [access, setAccess] = useState(null);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let refreshTimer = null;

    const loadAccess = async () => {
      try {
        setError("");
        const endpoint = testStream
          ? "/streams/test-access"
          : `/cameras/${cameraId}/stream-access?profile=${profile}`;
        const result = await api(endpoint);
        if (cancelled) return;
        setAccess(result);
        setRetryCount(0);
        const expiresAt = new Date(result.expires_at).getTime();
        const tokenRefreshIn = Math.max(30000, expiresAt - Date.now() - 45000);
        const reconnectIn = result.ready === false ? 5000 : tokenRefreshIn;
        refreshTimer = window.setTimeout(loadAccess, reconnectIn);
      } catch (loadError) {
        if (cancelled) return;
        setAccess(null);
        const nextRetry = retryCount + 1;
        setRetryCount(nextRetry);
        setError(loadError.message || "Não foi possível autorizar este vídeo.");
        if (nextRetry <= 3) {
          refreshTimer = window.setTimeout(loadAccess, Math.min(10000, nextRetry * 2500));
        }
      }
    };

    if (testStream || cameraId) loadAccess();
    return () => {
      cancelled = true;
      if (refreshTimer) window.clearTimeout(refreshTimer);
    };
  }, [cameraId, profile, testStream, reloadKey]);

  if (error && !access) {
    return (
      <div className="secureStreamState error">
        <ShieldCheck size={24} />
        <b>Vídeo indisponível</b>
        <span>{retryCount <= 3 ? `Reconectando automaticamente… tentativa ${retryCount}/3` : error}</span>
        <button type="button" onClick={() => { setRetryCount(0); setReloadKey((value) => value + 1); }}>Tentar novamente</button>
      </div>
    );
  }

  if (!access) {
    return (
      <div className="secureStreamState loading">
        <RefreshCw size={24} />
        <b>Conectando ao stream {profile}...</b>
      </div>
    );
  }

  return (
    <iframe
      key={`${access.webrtc_url}-${reloadKey}`}
      src={access.webrtc_url}
      title={title}
      loading="lazy"
      allow="autoplay; fullscreen; picture-in-picture"
      referrerPolicy="same-origin"
      onError={() => setReloadKey((value) => value + 1)}
    />
  );
}

const MENU = [
  ["Painel Geral", LayoutDashboard, "dashboard"],
  ["Central Operacional", Siren, "operations"],
  ["Escolas", Building2, "schools"],
  ["Câmeras", Camera, "cameras"],
  ["Eventos & Saúde", Activity, "camera-events"],
  ["Monitoramento", Video, "monitor"],
  ["Mapa Operacional", MapPinned, "maps"],
  ["Plantas Baixas", FileImage, "floorplans"],
  ["Video Wall", LayoutDashboard, "video-wall"],
  ["Playback e Evidências", History, "playback"],
  ["Central de Alertas", AlertTriangle, "alerts"],
  ["Ocorrências", ClipboardList, "occurrences"],
  ["Despacho", Truck, "dispatch"],
  ["Equipamentos", Server, "equipment"],
  ["Relatórios", BarChart3, "reports"],
  ["Auditoria", ShieldCheck, "audit"],
  ["Segurança", ShieldCheck, "security"],
  ["Infraestrutura", Server, "infrastructure"],
  ["Configurações", Settings, "settings"],
  ["Homologação", Wrench, "homologation"],
];

const ROLE_OPTIONS = [
  ["ADMIN_SECRETARIA", "Administrador da Secretaria", "SECRETARIA"],
  ["GESTOR_SECRETARIA", "Gestor da Secretaria", "SECRETARIA"],
  ["SUPERVISOR_GUARDA", "Supervisor da Guarda", "GUARDA"],
  ["OPERADOR_GUARDA", "Operador da Guarda", "GUARDA"],
  ["DESPACHANTE_GUARDA", "Despachante da Guarda", "GUARDA"],
  ["GESTOR_ESCOLA", "Gestor da Escola", "ESCOLA"],
  ["OPERADOR_ESCOLA", "Operador da Escola", "ESCOLA"],
  ["TECNICO", "Técnico", "SECRETARIA"],
];

const ROLE_LABELS = Object.fromEntries(ROLE_OPTIONS.map(([value, label]) => [value, label]));
const ROLE_ENVIRONMENTS = Object.fromEntries(ROLE_OPTIONS.map(([value, , environment]) => [value, environment]));
const SCHOOL_ROLES = new Set(["GESTOR_ESCOLA", "OPERADOR_ESCOLA"]);

function roleLabel(role) {
  return ROLE_LABELS[role] || role;
}

function roleEnvironment(role) {
  return ROLE_ENVIRONMENTS[role] || "";
}

const CAMERA_TILES = [
  ["Cam-01 Central", "Secretaria / Recepção"],
  ["Cam-02 Pátio 1", "Pátio principal"],
  ["Cam-03 Entrada Leste", "Entrada de alunos"],
  ["Cam-04 Estacionamento", "Área externa"],
];

function routeFromHash() {
  const value = window.location.hash.replace("#/", "").replace("#", "");
  return MENU.some(([, , key]) => key === value) ? value : "dashboard";
}


function ActionFeedbackBanner({ feedback, onClose }) {
  if (!feedback) return null;
  const isError = feedback.type === "error";
  const Icon = isError ? XCircle : CheckCircle2;
  return (
    <div
      className={`actionFeedbackBanner ${isError ? "error" : "success"}`}
      role={isError ? "alert" : "status"}
      aria-live={isError ? "assertive" : "polite"}
    >
      <div className="actionFeedbackContent">
        <Icon size={18} />
        <div>
          <strong>{feedback.title}</strong>
          {feedback.detail && <span>{feedback.detail}</span>}
        </div>
      </div>
      <button type="button" className="actionFeedbackClose" onClick={onClose} aria-label="Fechar mensagem">
        <XCircle size={17} />
      </button>
    </div>
  );
}

export default function App() {
  const [section, setSection] = useState(routeFromHash);
  const [dashboard, setDashboard] = useState({});
  const [schools, setSchools] = useState([]);
  const [cameras, setCameras] = useState([]);
  const cameraFleetStatus = useMemo(() => deriveCameraFleetStatus(cameras), [cameras]);
  const [alerts, setAlerts] = useState([]);
  const [cameraEvents, setCameraEvents] = useState([]);
  const [cameraHealth, setCameraHealth] = useState([]);
  const [recorderHealth, setRecorderHealth] = useState([]);
  const [cameraEventOverview, setCameraEventOverview] = useState({});
  const [occurrences, setOccurrences] = useState([]);
  const [teams, setTeams] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [equipment, setEquipment] = useState([]);
  const [reportData, setReportData] = useState({});
  const [settingsData, setSettingsData] = useState([]);
  const [authUser, setAuthUser] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("eduvigia_user") || "null");
    } catch {
      return null;
    }
  });
  const [authReady, setAuthReady] = useState(false);
  const [users, setUsers] = useState([]);
  const [loginForm, setLoginForm] = useState({
    email: "admin@eduvigia.local",
    password: "",
  });
  const [loginLoading, setLoginLoading] = useState(false);
  const [userForm, setUserForm] = useState({
    name: "",
    email: "",
    password: "",
    role: "OPERADOR_GUARDA",
    school_id: "",
    active: true,
  });
  const [passwordForm, setPasswordForm] = useState({
    current_password: "",
    new_password: "",
  });
  const [permissions, setPermissions] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [notificationOpen, setNotificationOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [supportOpen, setSupportOpen] = useState(false);
  const [supportInfo, setSupportInfo] = useState(null);
  const [supportMessage, setSupportMessage] = useState("");
  const [supportLoading, setSupportLoading] = useState(false);
  const [supportForm, setSupportForm] = useState({
    name: "",
    email: "",
    phone: "",
    category: "ACESSO",
    subject: "",
    message: "",
  });
  const [homologationChecklist, setHomologationChecklist] = useState(null);
  const [systemHealth, setSystemHealth] = useState(null);
  const [homologationData, setHomologationData] = useState(null);
  const [selectedOccurrence, setSelectedOccurrence] = useState(null);
  const [selectedSchool, setSelectedSchool] = useState(null);
  const [message, setMessage] = useState("");
  const [actionFeedback, setActionFeedback] = useState(null);
  const [actionBusy, setActionBusy] = useState({});
  const actionFeedbackTimer = useRef(null);
  const [globalSearch, setGlobalSearch] = useState("");
  const [schoolForm, setSchoolForm] = useState({
    code: "",
    name: "",
    address: "",
    neighborhood: "",
    city: "",
    phone: "",
    email: "",
    latitude: "",
    longitude: "",
    kit_type: "KIT_01",
    responsible: "",
    operational_status: "IMPLANTACAO",
    notes: "",
  });
  const [cameraForm, setCameraForm] = useState({
    school_id: "",
    name: "",
    location: "",
    ip_address: "",
    port: 554,
    username: "",
    password: "",
    manufacturer: "Hikvision",
    model: "",
    camera_type: "FIXA",
    rtsp_url: "",
    rtsp_url_main: "",
    rtsp_url_sub: "",
    stream_name: "",
    is_totem_camera: false,
    stream_profile: "SUB",
    source_type: "CAMERA_IP",
    device_id: "",
    logical_channel: 1,
    sensor_type: "VISIBLE",
    sensor_label: "",
    primary_sensor: true,
    recorder_id: "",
    nvr_channel: 1,
    codec: "H.264",
    resolution: "640x360",
    fps: 10,
    main_codec: "H.264",
    main_resolution: "1920x1080",
    main_fps: 15,
    main_bitrate_kbps: 4096,
    sub_codec: "H.264",
    sub_resolution: "640x360",
    sub_fps: 10,
    sub_bitrate_kbps: 512,
    ptz_enabled: false,
    ptz_protocol: "HIKVISION_ISAPI",
    ptz_http_port: 80,
    ptz_https: false,
    ptz_channel: 1,
  });
  const [recorders, setRecorders] = useState([]);
  const [videoDevices, setVideoDevices] = useState([]);
  const [deviceDiscovery, setDeviceDiscovery] = useState({});
  const [recorderDiscovery, setRecorderDiscovery] = useState(null);
  const [selectedImportChannels, setSelectedImportChannels] = useState([]);
  const [updateExistingChannels, setUpdateExistingChannels] = useState(false);
  const [editingSchoolId, setEditingSchoolId] = useState(null);
  const [editingRecorderId, setEditingRecorderId] = useState(null);
  const [editingCameraId, setEditingCameraId] = useState(null);

  const [recorderForm, setRecorderForm] = useState({
    school_id: "",
    name: "",
    manufacturer: "Hikvision",
    model: "",
    serial_number: "",
    ip_address: "",
    http_port: 80,
    https_port: 443,
    rtsp_port: 554,
    sdk_port: 8000,
    username: "",
    password: "",
    channel_count: 16,
    firmware: "",
    firmware_released_date: "",
    device_type: "",
    mac_address: "",
    notes: "",
  });
  const [videoDeviceForm, setVideoDeviceForm] = useState({
    school_id: "", name: "", manufacturer: "Hikvision", model: "", serial_number: "",
    ip_address: "", http_port: 80, https_port: 443, rtsp_port: 554, username: "", password: "",
    device_type: "BISPECTRUM", channel_count: 2,
  });
  const [occurrenceForm, setOccurrenceForm] = useState({
    school_name: "",
    category: "SEGURANCA",
    priority: "MEDIA",
    description: "",
    assigned_team: "",
  });
  const [teamForm, setTeamForm] = useState({
    name: "",
    team_type: "INTERNA",
    phone: "",
    notes: "",
  });
  const [equipmentForm, setEquipmentForm] = useState({
    school_id: "",
    category: "CAMERA",
    name: "",
    manufacturer: "",
    model: "",
    serial_number: "",
    asset_number: "",
    location: "",
    status: "OPERACIONAL",
    installed_at: "",
    warranty_until: "",
    notes: "",
  });

  const clearActionFeedback = () => {
    if (actionFeedbackTimer.current) {
      window.clearTimeout(actionFeedbackTimer.current);
      actionFeedbackTimer.current = null;
    }
    setActionFeedback(null);
  };

  const showActionFeedback = (type, title, detail = "") => {
    if (actionFeedbackTimer.current) window.clearTimeout(actionFeedbackTimer.current);
    setActionFeedback({ type, title, detail, id: Date.now() });
    const timeoutMs = type === "error" ? 8000 : 5000;
    actionFeedbackTimer.current = window.setTimeout(() => {
      setActionFeedback(null);
      actionFeedbackTimer.current = null;
    }, timeoutMs);
  };

  const runBusyAction = async (key, callback) => {
    setActionBusy((current) => ({ ...current, [key]: true }));
    try {
      return await callback();
    } finally {
      setActionBusy((current) => {
        const next = { ...current };
        delete next[key];
        return next;
      });
    }
  };

  useEffect(() => () => {
    if (actionFeedbackTimer.current) window.clearTimeout(actionFeedbackTimer.current);
  }, []);

  const refreshNotifications = async () => {
    try {
      const [notificationRows, unread] = await Promise.all([
        api("/notifications"),
        api("/notifications/unread-count"),
      ]);
      setNotifications(notificationRows);
      setUnreadCount(unread.unread || 0);
    } catch (error) {
      if (localStorage.getItem("eduvigia_token")) setMessage(error.message);
    }
  };

  const load = async () => {
    try {
      const [d, s, c, r, vd, a, ce, ch, rh, ceo, o, t, audit, eq, reports, settings, notificationRows, unread, health] = await Promise.all([
        api("/dashboard"),
        api("/schools"),
        api("/cameras"),
        api("/recorders"),
        api("/video-devices").catch(() => []),
        api("/alerts"),
        api("/camera-events?limit=200").catch(() => []),
        api("/camera-health").catch(() => []),
        api("/recorder-health").catch(() => []),
        api("/camera-events/overview").catch(() => ({})),
        api("/occurrences"),
        api("/teams").catch(() => []),
        api("/audit").catch(() => []),
        api("/equipment"),
        api("/reports/summary").catch(() => ({})),
        api("/settings").catch(() => []),
        api("/notifications"),
        api("/notifications/unread-count"),
        api("/system/health"),
      ]);
      setDashboard(d);
      setSchools(s);
      setCameras(c);
      setRecorders(r);
      setVideoDevices(vd);
      setAlerts(a);
      setCameraEvents(ce);
      setCameraHealth(ch);
      setRecorderHealth(rh);
      setCameraEventOverview(ceo);
      setOccurrences(o);
      setTeams(t);
      setAuditLogs(audit);
      setEquipment(eq);
      setReportData(reports);
      setSettingsData(settings);
      setNotifications(notificationRows);
      setUnreadCount(unread.unread || 0);
      setSystemHealth(health);
      if (["ADMIN_SECRETARIA", "TECNICO"].includes(authUser?.role || JSON.parse(localStorage.getItem("eduvigia_user") || "{}").role)) {
        setHomologationData(await api("/homologation").catch(() => null));
        setHomologationChecklist(
          await api("/homologation/checklist").catch(() => null)
        );
      }
      if (["ADMIN_SECRETARIA", "GESTOR_SECRETARIA"].includes(authUser?.role || JSON.parse(localStorage.getItem("eduvigia_user") || "{}").role)) {
        const userRows = await api("/users/overview");
        setUsers(userRows);
      }
      setMessage("");
      return true;
    } catch (error) {
      setMessage(error.message);
      return false;
    }
  };

  useEffect(() => {
    api("/support/info")
      .then(setSupportInfo)
      .catch(() => null);
  }, []);

  useEffect(() => {
    const bootstrap = async () => {
      const token = localStorage.getItem("eduvigia_token");
      if (!token) {
        setAuthReady(true);
        return;
      }
      try {
        const me = await api("/auth/me");
        setAuthUser(me);
        localStorage.setItem("eduvigia_user", JSON.stringify(me));
        if (me.must_change_password) {
          setPermissions([]);
        } else {
          const permissionData = await api("/auth/permissions");
          setPermissions(permissionData.permissions || []);
          await load();
        }
      } catch {
        setAuthUser(null);
      } finally {
        setAuthReady(true);
      }
    };
    bootstrap();

    const expired = () => {
      setAuthUser(null);
      setAuthReady(true);
    };
    window.addEventListener("eduvigia-auth-expired", expired);
    return () => window.removeEventListener("eduvigia-auth-expired", expired);
  }, []);

  useEffect(() => {
    if (!authUser) return undefined;
    const timer = window.setInterval(() => refreshNotifications(), 10000);
    const onFocus = () => refreshNotifications();
    window.addEventListener("focus", onFocus);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", onFocus);
    };
  }, [authUser?.id]);

  useEffect(() => {
    const onHash = () => setSection(routeFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const navigate = (key) => {
    window.location.hash = `/${key}`;
    setSection(key);
  };

  const filteredSchools = useMemo(() => {
    const term = globalSearch.trim().toLowerCase();
    if (!term) return schools;
    return schools.filter(
      (school) =>
        school.name.toLowerCase().includes(term) ||
        school.address.toLowerCase().includes(term)
    );
  }, [schools, globalSearch]);

  const schoolName = (id) =>
    schools.find((school) => school.id === id)?.name || "Escola não localizada";

  const emptySchoolForm = () => ({
    code: "",
    name: "",
    address: "",
    neighborhood: "",
    city: "",
    phone: "",
    email: "",
    latitude: "",
    longitude: "",
    kit_type: "KIT_01",
    responsible: "",
    operational_status: "IMPLANTACAO",
    notes: "",
  });

  const saveSchool = async (event) => {
    event.preventDefault();
    const wasEditing = Boolean(editingSchoolId);
    return runBusyAction("school-save", async () => {
      try {
        await api(editingSchoolId ? `/schools/${editingSchoolId}` : "/schools", {
          method: editingSchoolId ? "PUT" : "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(schoolForm),
        });
        setSchoolForm(emptySchoolForm());
        setEditingSchoolId(null);
        await load();
        showActionFeedback("success", wasEditing ? "Escola atualizada" : "Escola cadastrada", "Operação concluída com sucesso.");
      } catch (error) {
        showActionFeedback("error", "Falha ao salvar escola", error.message || "Não foi possível concluir a operação.");
      }
    });
  };

  const editSchool = (school) => {
    setEditingSchoolId(school.id);
    setSchoolForm({
      code: school.code || "",
      name: school.name || "",
      address: school.address || "",
      neighborhood: school.neighborhood || "",
      city: school.city || "",
      phone: school.phone || "",
      email: school.email || "",
      latitude: school.latitude || "",
      longitude: school.longitude || "",
      kit_type: school.kit_type || "KIT_01",
      responsible: school.responsible || "",
      operational_status: school.operational_status || "IMPLANTACAO",
      notes: school.notes || "",
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const cancelSchoolEdit = () => {
    setEditingSchoolId(null);
    setSchoolForm(emptySchoolForm());
  };

  const discoverRecorder = async (id) => {
    try {
      setMessage("Consultando informações, canais e perfis do gravador...");
      const result = await api(`/recorders/${id}/discover?include_capabilities=true`, { method: "POST" });
      setRecorderDiscovery(result);
      setUpdateExistingChannels(false);
      setSelectedImportChannels(
        result.channels
          .filter((channel) => channel.enabled !== false)
          .map((channel) => {
            const sub = channel.capabilities?.SUB || {};
            const main = channel.capabilities?.MAIN || {};
            const fpsRaw = Number(sub.max_frame_rate || main.max_frame_rate || 10);
            const normalizedFps = fpsRaw > 100 ? Math.max(1, Math.round(fpsRaw / 100)) : Math.max(1, Math.round(fpsRaw || 10));
            return {
              channel: channel.channel,
              name: channel.name,
              location: channel.name,
              camera_type: "FIXA",
              codec: sub.video_codec_type || main.video_codec_type || "H.264",
              resolution: sub.resolution || main.resolution || "640x360",
              fps: normalizedFps,
              main_codec: main.video_codec_type || "H.264",
              main_resolution: main.resolution || "1920x1080",
              main_fps: (() => { const raw = Number(main.max_frame_rate || 15); return raw > 100 ? Math.max(1, Math.round(raw / 100)) : Math.max(1, Math.round(raw || 15)); })(),
              main_bitrate_kbps: Number(main.max_bitrate || main.bitrate || 4096),
              sub_codec: sub.video_codec_type || "H.264",
              sub_resolution: sub.resolution || "640x360",
              sub_fps: normalizedFps,
              sub_bitrate_kbps: Number(sub.max_bitrate || sub.bitrate || 512),
              selected: channel.online !== false && !channel.configured,
              configured: Boolean(channel.configured),
              online: channel.online !== false,
              ip_address: channel.ip_address || "",
              capabilities: channel.capabilities || null,
            };
          })
      );
      setMessage(`${result.channel_count} canal(is) identificado(s); ${result.configured_count || 0} já configurado(s).`);
      await load();
    } catch (error) {
      setMessage(error.message);
    }
  };

  const importDiscoveredChannels = async () => {
    if (!recorderDiscovery) return;
    const channels = selectedImportChannels
      .filter((item) => item.selected)
      .map(({ selected, configured, online, ip_address, capabilities, ...item }) => item);
    if (!channels.length) {
      setMessage("Selecione pelo menos um canal.");
      return;
    }
    try {
      const result = await api(
        `/recorders/${recorderDiscovery.recorder_id}/import-channels`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            channels,
            update_existing: updateExistingChannels,
            test_after_import: false,
          }),
        }
      );
      setMessage(`${result.created} criado(s), ${result.updated} atualizado(s), ${result.skipped} ignorado(s), ${result.failed} falha(s).`);
      setRecorderDiscovery(null);
      setSelectedImportChannels([]);
      setUpdateExistingChannels(false);
      await load();
    } catch (error) {
      setMessage(error.message);
    }
  };

  const resetRecorderForm = () => {
    setEditingRecorderId(null);
    setRecorderForm({
      school_id: "",
      name: "",
      manufacturer: "Hikvision",
      model: "",
      serial_number: "",
      ip_address: "",
      http_port: 80,
      https_port: 443,
      rtsp_port: 554,
      sdk_port: 8000,
      username: "",
      password: "",
      channel_count: 16,
      firmware: "",
      firmware_released_date: "",
      device_type: "",
      mac_address: "",
      notes: "",
    });
  };

  const createRecorder = async (event) => {
    event.preventDefault();
    try {
      const payload = {
        ...recorderForm,
        school_id: Number(recorderForm.school_id),
        http_port: Number(recorderForm.http_port),
        https_port: Number(recorderForm.https_port),
        rtsp_port: Number(recorderForm.rtsp_port),
        sdk_port: Number(recorderForm.sdk_port),
        channel_count: Number(recorderForm.channel_count),
      };
      await api(editingRecorderId ? `/recorders/${editingRecorderId}` : "/recorders", {
        method: editingRecorderId ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const action = editingRecorderId ? "atualizado" : "cadastrado";
      resetRecorderForm();
      await load();
      setMessage(`Gravador ${action} com sucesso.`);
    } catch (error) {
      setMessage(error.message);
    }
  };

  const editRecorder = (recorder) => {
    setEditingRecorderId(recorder.id);
    setRecorderForm({
      school_id: String(recorder.school_id || ""),
      name: recorder.name || "",
      manufacturer: recorder.manufacturer || "Hikvision",
      model: recorder.model || "",
      serial_number: recorder.serial_number || "",
      ip_address: recorder.ip_address || "",
      http_port: recorder.http_port || 80,
      https_port: recorder.https_port || 443,
      rtsp_port: recorder.rtsp_port || 554,
      sdk_port: recorder.sdk_port || 8000,
      username: recorder.username || "",
      password: "",
      channel_count: recorder.channel_count || 16,
      firmware: recorder.firmware || "",
      firmware_released_date: recorder.firmware_released_date || "",
      device_type: recorder.device_type || "",
      mac_address: recorder.mac_address || "",
      notes: recorder.notes || "",
    });
  };

  const testRecorder = async (id) => runBusyAction(`recorder-test-${id}`, async () => {
    try {
      const result = await api(`/recorders/${id}/test`, { method: "POST" });
      const rtsp = result.tests?.RTSP?.ok ? "RTSP OK" : "RTSP falhou";
      const isapi = result.tests?.ISAPI?.ok ? "ISAPI autenticado" : "ISAPI indisponível";
      showActionFeedback("success", "Teste do gravador concluído", `Status ${result.status}: ${rtsp}; ${isapi}.`);
      await load();
    } catch (error) {
      showActionFeedback("error", "Falha no teste do gravador", error.message || "Não foi possível testar o equipamento.");
    }
  });

  const testRecorderChannels = async (id) => runBusyAction(`recorder-channels-${id}`, async () => {
    try {
      const result = await api(`/recorders/${id}/test-channels`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile: "BOTH", provision: true }),
      });
      showActionFeedback("success", "Teste dos canais concluído", `${result.online} de ${result.tested} canal(is) online; ${result.offline} offline.`);
      await load();
    } catch (error) {
      showActionFeedback("error", "Falha no teste dos canais", error.message || "Não foi possível testar MAIN/SUB.");
    }
  });

  const reprovisionRecorder = async (id) => runBusyAction(`recorder-reprovision-${id}`, async () => {
    try {
      const result = await api(`/recorders/${id}/reprovision`, { method: "POST" });
      const detail = `${result.provisioned} de ${result.total} canal(is) reprovisionado(s); ${result.failed} falha(s).`;
      showActionFeedback(result.failed ? "error" : "success", result.failed ? "Reprovisionamento concluído com falhas" : "Reprovisionamento concluído", detail);
      await load();
    } catch (error) {
      showActionFeedback("error", "Falha ao reprovisionar gravador", error.message || "Não foi possível publicar os streams.");
    }
  });

  const deleteRecorder = async (id) => {
    if (!window.confirm("Excluir este gravador?")) return;
    try {
      await api(`/recorders/${id}`, { method: "DELETE" });
      await load();
      setMessage("Gravador excluído.");
    } catch (error) {
      setMessage(error.message);
    }
  };

  const resetVideoDeviceForm = () => setVideoDeviceForm({
    school_id: "", name: "", manufacturer: "Hikvision", model: "", serial_number: "",
    ip_address: "", http_port: 80, https_port: 443, rtsp_port: 554, username: "", password: "",
    device_type: "BISPECTRUM", channel_count: 2,
  });

  const createVideoDevice = async (event) => {
    event.preventDefault();
    try {
      await api("/video-devices", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
        ...videoDeviceForm, school_id: Number(videoDeviceForm.school_id), http_port: Number(videoDeviceForm.http_port || 80),
        https_port: Number(videoDeviceForm.https_port || 443), rtsp_port: Number(videoDeviceForm.rtsp_port || 554), channel_count: Number(videoDeviceForm.channel_count || 1),
      })});
      resetVideoDeviceForm(); await load(); setMessage("Dispositivo físico cadastrado. Agora adicione os canais/sensores.");
    } catch (error) { setMessage(error.message); }
  };

  const discoverVideoDevice = async (id) => {
    try {
      const result = await api(`/video-devices/${id}/discover`, { method: "POST" });
      setDeviceDiscovery((current) => ({ ...current, [id]: result.channels || [] }));
      setMessage(`${(result.channels || []).length} canal(is) lógico(s) detectado(s) no dispositivo.`);
      await load();
    } catch (error) { setMessage(error.message); }
  };

  const deleteVideoDevice = async (id) => {
    try { await api(`/video-devices/${id}`, { method: "DELETE" }); await load(); } catch (error) { setMessage(error.message); }
  };

  const resetCameraForm = () => {
    setEditingCameraId(null);
    setCameraForm({
      school_id: "",
      name: "",
      location: "",
      ip_address: "",
      port: 554,
      username: "",
      password: "",
      manufacturer: "Hikvision",
      model: "",
      camera_type: "FIXA",
      rtsp_url: "",
      stream_name: "",
      is_totem_camera: false,
      stream_profile: "SUB",
      source_type: "CAMERA_IP",
      device_id: "",
      logical_channel: 1,
      sensor_type: "VISIBLE",
      sensor_label: "",
      primary_sensor: true,
      recorder_id: "",
      nvr_channel: 1,
      codec: "H.264",
      resolution: "640x360",
      fps: 10,
      main_codec: "H.264",
      main_resolution: "1920x1080",
      main_fps: 15,
      main_bitrate_kbps: 4096,
      sub_codec: "H.264",
      sub_resolution: "640x360",
      sub_fps: 10,
      sub_bitrate_kbps: 512,
      ptz_enabled: false,
      ptz_protocol: "HIKVISION_ISAPI",
      ptz_http_port: 80,
      ptz_https: false,
      ptz_channel: 1,
    });
  };

  const createCamera = async (event) => {
    event.preventDefault();
    try {
      const payload = {
        ...cameraForm,
        school_id: Number(cameraForm.school_id),
        recorder_id: cameraForm.recorder_id ? Number(cameraForm.recorder_id) : null,
        device_id: cameraForm.device_id ? Number(cameraForm.device_id) : null,
        logical_channel: Number(cameraForm.logical_channel || 1),
        sensor_type: cameraForm.sensor_type || "VISIBLE",
        sensor_label: cameraForm.sensor_label || null,
        primary_sensor: Boolean(cameraForm.primary_sensor),
        nvr_channel: Number(cameraForm.nvr_channel || 1),
        port: Number(cameraForm.port || 554),
        stream_profile: "SUB",
        codec: cameraForm.sub_codec || cameraForm.codec || "H.264",
        resolution: cameraForm.sub_resolution || cameraForm.resolution || null,
        fps: cameraForm.sub_fps ? Number(cameraForm.sub_fps) : null,
        main_fps: cameraForm.main_fps ? Number(cameraForm.main_fps) : null,
        main_bitrate_kbps: cameraForm.main_bitrate_kbps ? Number(cameraForm.main_bitrate_kbps) : null,
        sub_fps: cameraForm.sub_fps ? Number(cameraForm.sub_fps) : null,
        sub_bitrate_kbps: cameraForm.sub_bitrate_kbps ? Number(cameraForm.sub_bitrate_kbps) : null,
        ptz_enabled: Boolean(cameraForm.ptz_enabled),
        ptz_protocol: "HIKVISION_ISAPI",
        ptz_http_port: Number(cameraForm.ptz_http_port || 80),
        ptz_https: Boolean(cameraForm.ptz_https),
        ptz_channel: Number((["NVR", "DVR"].includes(cameraForm.source_type) ? cameraForm.nvr_channel : cameraForm.ptz_channel) || 1),
        stream_name: editingCameraId ? cameraForm.stream_name || null : null,
      };
      await api(editingCameraId ? `/cameras/${editingCameraId}` : "/cameras", {
        method: editingCameraId ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const action = editingCameraId ? "atualizada" : "cadastrada";
      resetCameraForm();
      await load();
      setMessage(`Câmera ${action} com sucesso.`);
    } catch (error) {
      setMessage(error.message);
    }
  };

  const editCamera = (camera) => {
    setEditingCameraId(camera.id);
    setCameraForm({
      school_id: String(camera.school_id || ""),
      name: camera.name || "",
      location: camera.location || "",
      ip_address: camera.ip_address || "",
      port: camera.port || 554,
      username: camera.username || "",
      password: "",
      manufacturer: camera.manufacturer || "Hikvision",
      model: camera.model || "",
      camera_type: camera.camera_type || "FIXA",
      rtsp_url: "",
      rtsp_url_main: "",
      rtsp_url_sub: "",
      stream_name: camera.stream_name || "",
      is_totem_camera: Boolean(camera.is_totem_camera),
      stream_profile: "SUB",
      source_type: camera.source_type || "CAMERA_IP",
      device_id: camera.device_id ? String(camera.device_id) : "",
      logical_channel: camera.logical_channel || 1,
      sensor_type: camera.sensor_type || "VISIBLE",
      sensor_label: camera.sensor_label || "",
      primary_sensor: camera.primary_sensor !== false,
      recorder_id: camera.recorder_id ? String(camera.recorder_id) : "",
      nvr_channel: camera.nvr_channel || 1,
      codec: camera.codec || camera.sub_codec || "H.264",
      resolution: camera.resolution || camera.sub_resolution || "640x360",
      fps: camera.fps || camera.sub_fps || 10,
      main_codec: camera.main_codec || "H.264",
      main_resolution: camera.main_resolution || "1920x1080",
      main_fps: camera.main_fps || 15,
      main_bitrate_kbps: camera.main_bitrate_kbps || 4096,
      sub_codec: camera.sub_codec || camera.codec || "H.264",
      sub_resolution: camera.sub_resolution || camera.resolution || "640x360",
      sub_fps: camera.sub_fps || camera.fps || 10,
      sub_bitrate_kbps: camera.sub_bitrate_kbps || 512,
      ptz_enabled: Boolean(camera.ptz_enabled),
      ptz_protocol: camera.ptz_protocol || "HIKVISION_ISAPI",
      ptz_http_port: camera.ptz_http_port || 80,
      ptz_https: Boolean(camera.ptz_https),
      ptz_channel: camera.ptz_channel || camera.nvr_channel || 1,
    });
  };

  const createOccurrence = async (event) => {
    event.preventDefault();
    try {
      await api("/occurrences", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(occurrenceForm),
      });
      setOccurrenceForm({
        school_name: "",
        category: "SEGURANCA",
        priority: "MEDIA",
        description: "",
        assigned_team: "",
      });
      await load();
      setMessage("Ocorrência aberta com sucesso.");
    } catch (error) {
      setMessage(error.message);
    }
  };

  const alertAction = async (id, action) => {
    try {
      await api(`/alerts/${id}/${action}`, { method: "PATCH" });
      await load();
    } catch (error) {
      setMessage(error.message);
    }
  };

  const alertToOccurrence = async (id) => {
    try {
      await api(`/alerts/${id}/occurrence`, { method: "POST" });
      await load();
      navigate("occurrences");
    } catch (error) {
      setMessage(error.message);
    }
  };

  const updateOccurrence = async (id, status, assignedTeam = null) => {
    try {
      await api(`/occurrences/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          status,
          assigned_team: assignedTeam,
        }),
      });
      await load();
    } catch (error) {
      setMessage(error.message);
    }
  };

  const toggleSchool = async (id) => {
    try {
      await api(`/schools/${id}/toggle`, { method: "PATCH" });
      await load();
    } catch (error) {
      setMessage(error.message);
    }
  };

  const testCamera = async (id) => runBusyAction(`camera-test-${id}`, async () => {
    try {
      const result = await api(`/cameras/${id}/test`, { method: "POST" });
      const main = result.profiles?.MAIN?.ok ? "MAIN OK" : "MAIN falhou";
      const sub = result.profiles?.SUB?.ok ? "SUB OK" : "SUB falhou";
      const ok = result.profiles?.MAIN?.ok && result.profiles?.SUB?.ok && result.provisioned;
      showActionFeedback(ok ? "success" : "error", ok ? "Teste da câmera concluído" : "Teste da câmera encontrou falhas", `Status ${result.status}: ${main}; ${sub}; MediaMTX ${result.provisioned ? "OK" : "com falha"}.`);
      await load();
    } catch (error) {
      showActionFeedback("error", "Falha no teste da câmera", error.message || "Não foi possível testar MAIN/SUB.");
    }
  });

  const testAllCameras = async () => runBusyAction("camera-test-all", async () => {
    try {
      const result = await api("/cameras/test-batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ camera_ids: null, provision: true }),
      });
      const ok = Number(result.offline || 0) === 0;
      showActionFeedback(ok ? "success" : "error", ok ? "Teste em lote concluído" : "Teste em lote encontrou câmeras offline", `${result.online} de ${result.tested} câmera(s) online; ${result.offline} offline.`);
      await load();
    } catch (error) {
      showActionFeedback("error", "Falha no teste em lote", error.message || "Não foi possível testar as câmeras.");
    }
  });

  const deleteCamera = async (id) => {
    if (!window.confirm("Excluir esta câmera?")) return;
    try {
      await api(`/cameras/${id}`, { method: "DELETE" });
      await load();
      setMessage("Câmera removida.");
    } catch (error) {
      setMessage(error.message);
    }
  };

  const createTeam = async (event) => {
    event.preventDefault();
    try {
      await api("/teams", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(teamForm),
      });
      setTeamForm({ name: "", team_type: "INTERNA", phone: "", notes: "" });
      await load();
      setMessage("Equipe cadastrada com sucesso.");
    } catch (error) {
      setMessage(error.message);
    }
  };

  const updateTeamStatus = async (id, status) => {
    try {
      await api(`/teams/${id}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      await load();
    } catch (error) {
      setMessage(error.message);
    }
  };

  const createEquipment = async (event) => {
    event.preventDefault();
    try {
      await api("/equipment", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...equipmentForm,
          school_id: equipmentForm.school_id ? Number(equipmentForm.school_id) : null,
          installed_at: equipmentForm.installed_at || null,
          warranty_until: equipmentForm.warranty_until || null,
        }),
      });
      setEquipmentForm({
        school_id: "",
        category: "CAMERA",
        name: "",
        manufacturer: "",
        model: "",
        serial_number: "",
        asset_number: "",
        location: "",
        status: "OPERACIONAL",
        installed_at: "",
        warranty_until: "",
        notes: "",
      });
      await load();
      setMessage("Equipamento cadastrado com sucesso.");
    } catch (error) {
      setMessage(error.message);
    }
  };

  const deleteEquipment = async (id) => {
    if (!window.confirm("Excluir este equipamento?")) return;
    try {
      await api(`/equipment/${id}`, { method: "DELETE" });
      await load();
      setMessage("Equipamento removido.");
    } catch (error) {
      setMessage(error.message);
    }
  };

  const openMaintenance = async (id) => {
    const description = window.prompt("Descreva a manutenção necessária:");
    if (!description) return;
    try {
      await api(`/equipment/${id}/maintenance`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          maintenance_type: "CORRETIVA",
          description,
          technician: "",
          status: "ABERTA",
          scheduled_at: null,
        }),
      });
      await load();
      setMessage("Manutenção registrada.");
    } catch (error) {
      setMessage(error.message);
    }
  };

  const saveSetting = async (key, value, description) => runBusyAction(`setting-${key}`, async () => {
    try {
      await api(`/settings/${key}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value, description }),
      });
      await load();
      showActionFeedback("success", "Configuração salva", description || key);
    } catch (error) {
      showActionFeedback("error", "Falha ao salvar configuração", error.message || "Não foi possível salvar a configuração.");
    }
  });

  const openSupport = (preset = {}) => {
    setSupportMessage("");
    setSupportForm((current) => ({
      ...current,
      name: current.name || authUser?.name || "",
      email: current.email || authUser?.email || loginForm.email || "",
      category: preset.category || current.category || "ACESSO",
      subject: preset.subject || current.subject || "",
      message: preset.message || current.message || "",
    }));
    setSupportOpen(true);
  };

  const openPasswordRecovery = () => {
    openSupport({
      category: "SENHA",
      subject: "Solicitação de recuperação de senha",
      message:
        "Não consigo acessar minha conta e preciso de orientação para redefinir a senha.",
    });
  };

  const submitSupport = async (event) => {
    event.preventDefault();
    setSupportLoading(true);
    setSupportMessage("");
    try {
      const result = await api("/support/requests", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(supportForm),
      });
      setSupportMessage(`Solicitação registrada. Protocolo: ${result.protocol}`);
      setSupportForm({
        name: "",
        email: loginForm.email || "",
        phone: "",
        category: "ACESSO",
        subject: "",
        message: "",
      });
    } catch (error) {
      setSupportMessage(error.message);
    } finally {
      setSupportLoading(false);
    }
  };

  const login = async (event) => {
    event.preventDefault();
    setLoginLoading(true);
    setMessage("");
    try {
      const result = await api("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(loginForm),
      });
      localStorage.setItem("eduvigia_token", result.token);
      localStorage.setItem("eduvigia_user", JSON.stringify(result.user));
      setAuthUser(result.user);
      if (result.user.must_change_password) {
        setPermissions([]);
      } else {
        const permissionData = await api("/auth/permissions");
        setPermissions(permissionData.permissions || []);
        await load();
      }
    } catch (error) {
      setMessage(error.message);
    } finally {
      setLoginLoading(false);
    }
  };

  const logout = async () => {
    try {
      await api("/auth/logout", { method: "POST" });
    } catch {
      // Sessão local será encerrada mesmo se a API estiver indisponível.
    }
    localStorage.removeItem("eduvigia_token");
    localStorage.removeItem("eduvigia_user");
    setAuthUser(null);
    setUsers([]);
    setPermissions([]);
  };

  const createUser = async (event) => {
    event.preventDefault();
    try {
      await api("/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...userForm,
          school_id: userForm.school_id ? Number(userForm.school_id) : null,
        }),
      });
      setUserForm({
        name: "",
        email: "",
        password: "",
        role: "OPERADOR_GUARDA",
        school_id: "",
        active: true,
      });
      const rows = await api("/users/overview");
      setUsers(rows);
      setMessage("Usuário cadastrado com sucesso.");
    } catch (error) {
      setMessage(error.message);
    }
  };

  const updateUser = async (id, values) => {
    try {
      await api(`/users/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: values.name,
          email: values.email,
          role: values.role,
          school_id: values.school_id ? Number(values.school_id) : null,
          active: Boolean(values.active),
        }),
      });
      const rows = await api("/users/overview");
      setUsers(rows);
      setMessage("Usuário atualizado com sucesso.");
      return true;
    } catch (error) {
      setMessage(error.message);
      return false;
    }
  };

  const resetUserPassword = async (id) => {
    const newPassword = window.prompt("Digite a nova senha temporária (mínimo 10 caracteres, com maiúscula, minúscula, número e símbolo):");
    if (!newPassword) return;
    try {
      await api(`/users/${id}/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ new_password: newPassword }),
      });
      setMessage("Senha redefinida. O usuário deverá alterá-la no próximo acesso.");
    } catch (error) {
      setMessage(error.message);
    }
  };

  const changePassword = async (event) => {
    event.preventDefault();
    try {
      await api("/auth/change-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(passwordForm),
      });
      const updated = { ...authUser, must_change_password: false };
      setAuthUser(updated);
      localStorage.setItem("eduvigia_user", JSON.stringify(updated));
      setPasswordForm({ current_password: "", new_password: "" });
      const permissionData = await api("/auth/permissions");
      setPermissions(permissionData.permissions || []);
      setMessage("Senha alterada com sucesso. O ambiente foi liberado.");
      await load();
    } catch (error) {
      setMessage(error.message);
    }
  };

  const can = (permission) =>
    permissions.includes("*") || permissions.includes(permission);

  const visibleMenu = MENU.filter(([, , key]) => {
    const map = {
      dashboard: "dashboard:view",
      operations: "command:view",
      schools: "schools:view",
      cameras: "cameras:view",
      "camera-events": "events:view",
      monitor: "monitor:view",
      maps: "maps:view",
      floorplans: "floorplans:view",
      "video-wall": "wall:view",
      playback: "playback:view",
      alerts: "alerts:view",
      occurrences: "occurrences:view",
      dispatch: "dispatch:view",
      equipment: "equipment:view",
      reports: "reports:view",
      audit: "audit:view",
      security: "users:view",
      settings: "settings:view",
      infrastructure: "infrastructure:view",
      homologation: "homologation:view",
    };
    return can(map[key]);
  });

  const openSchoolDetails = async (id) => {
    try {
      setSelectedSchool(await api(`/schools/${id}/details`));
    } catch (error) {
      setMessage(error.message);
    }
  };

  const openOccurrenceDetails = async (id) => {
    try {
      setSelectedOccurrence(await api(`/occurrences/${id}/details`));
    } catch (error) {
      setMessage(error.message);
    }
  };

  const provisionCamera = async (id) => runBusyAction(`camera-provision-${id}`, async () => {
    try {
      const result = await api(`/cameras/${id}/provision`, { method: "POST" });
      if (result.ok) {
        showActionFeedback("success", "Streams publicados", `Stream ${result.stream_name} configurado no MediaMTX.`);
      } else {
        showActionFeedback("error", "Falha ao publicar streams", result.detail || "O MediaMTX não confirmou a publicação.");
      }
      await load();
    } catch (error) {
      showActionFeedback("error", "Falha ao publicar streams", error.message || "Não foi possível configurar o MediaMTX.");
    }
  });

  const snapshotOccurrence = async (occurrenceId, cameraId) => {
    try {
      const form = new FormData();
      form.append("camera_id", String(cameraId));
      form.append("observation", "Snapshot capturado pelo monitoramento.");
      const token = localStorage.getItem("eduvigia_token");
      const response = await fetch(`${API_URL}/occurrences/${occurrenceId}/snapshot`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail || "Falha ao capturar snapshot");
      setMessage("Snapshot anexado à ocorrência.");
      setSelectedOccurrence(await api(`/occurrences/${occurrenceId}/details`));
    } catch (error) {
      setMessage(error.message);
    }
  };

  const addOccurrenceNote = async (occurrenceId) => {
    const description = window.prompt("Digite a observação ou conclusão:");
    if (!description) return;
    try {
      await api(`/occurrences/${occurrenceId}/events`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ event_type: "CONCLUSAO", description }),
      });
      setSelectedOccurrence(await api(`/occurrences/${occurrenceId}/details`));
      setMessage("Registro incluído na linha do tempo.");
    } catch (error) {
      setMessage(error.message);
    }
  };

  const readNotification = async (item) => {
    try {
      if (!item.read_at) {
        await api(`/notifications/${item.id}/read`, { method: "PATCH" });
        setNotifications((current) =>
          current.map((row) =>
            row.id === item.id ? { ...row, read_at: new Date().toISOString() } : row
          )
        );
        setUnreadCount((current) => Math.max(0, current - 1));
      }
      const targetByEntity = { alert: "alerts", occurrence: "occurrences", school: "schools", equipment: "equipment" };
      const target = targetByEntity[item.entity_type];
      if (target) {
        setNotificationOpen(false);
        navigate(target);
      }
    } catch (error) {
      setMessage(error.message);
    }
  };

  const readAllNotifications = async () => {
    try {
      await api("/notifications/read-all", { method: "PATCH" });
      setNotifications((current) =>
        current.map((item) => ({ ...item, read_at: item.read_at || new Date().toISOString() }))
      );
      setUnreadCount(0);
    } catch (error) {
      setMessage(error.message);
    }
  };

  const downloadReport = async (path, filename) => {
    try {
      const token = localStorage.getItem("eduvigia_token");
      const response = await fetch(`${API_URL}${path}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || "Falha ao exportar relatório");
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      setMessage(error.message);
    }
  };

  const supportDialog = supportOpen ? (
          <DetailModal title="Fale com o suporte" onClose={() => setSupportOpen(false)}>
            <form className="supportForm" onSubmit={submitSupport}>
              <div className="supportIntro">
                <Headphones size={30} />
                <div>
                  <b>{supportInfo?.title || "Suporte EduVigIA"}</b>
                  <span>Descreva o problema. Um protocolo será gerado.</span>
                </div>
              </div>

              {supportMessage && <div className="supportResult">{supportMessage}</div>}

              <div className="formGrid">
                <Field label="Nome">
                  <input required value={supportForm.name} onChange={(e) => setSupportForm({ ...supportForm, name: e.target.value })} />
                </Field>
                <Field label="E-mail">
                  <input required type="email" value={supportForm.email} onChange={(e) => setSupportForm({ ...supportForm, email: e.target.value })} />
                </Field>
                <Field label="Telefone">
                  <input value={supportForm.phone} onChange={(e) => setSupportForm({ ...supportForm, phone: e.target.value })} />
                </Field>
                <Field label="Categoria">
                  <select value={supportForm.category} onChange={(e) => setSupportForm({ ...supportForm, category: e.target.value })}>
                    <option value="ACESSO">Acesso ao sistema</option>
                    <option value="SENHA">Senha</option>
                    <option value="ERRO">Erro no sistema</option>
                    <option value="CAMERA">Câmera</option>
                    <option value="NVR">NVR/DVR</option>
                    <option value="OUTRO">Outro</option>
                  </select>
                </Field>
                <Field label="Assunto">
                  <input required value={supportForm.subject} onChange={(e) => setSupportForm({ ...supportForm, subject: e.target.value })} />
                </Field>
              </div>

              <Field label="Descrição">
                <textarea
                  required
                  rows="6"
                  value={supportForm.message}
                  onChange={(e) => setSupportForm({ ...supportForm, message: e.target.value })}
                  placeholder="Informe o que aconteceu, em qual tela e qual mensagem apareceu."
                />
              </Field>

              <div className="supportChannels">
                <span><Mail size={15} /> {supportInfo?.email || "suporte@eduvigia.local"}</span>
                <span><Phone size={15} /> {supportInfo?.phone || "(81) 0000-0000"}</span>
                <span>{supportInfo?.hours || "Segunda a sexta, das 08h às 18h"}</span>
              </div>

              <div className="modalFooter">
                <button type="button" onClick={() => setSupportOpen(false)}>Fechar</button>
                <button type="submit" className="primaryButton" disabled={supportLoading}>
                  {supportLoading ? "Enviando..." : "Abrir solicitação"}
                </button>
              </div>
            </form>
          </DetailModal>
  ) : null;

  if (!authReady) {
    return <div className="authLoading">Carregando EduVigIA...</div>;
  }

  if (!authUser) {
    return (
      <>
        <LoginPage
          form={loginForm}
          setForm={setLoginForm}
          onSubmit={login}
          message={message}
          loading={loginLoading}
          onSupport={() => openSupport()}
          onForgotPassword={openPasswordRecovery}
        />
        {supportDialog}
      </>
    );
  }

  if (authUser.must_change_password) {
    return (
      <>
        <PasswordChangeGate
          user={authUser}
          form={passwordForm}
          setForm={setPasswordForm}
          onSubmit={changePassword}
          onLogout={logout}
          onSupport={() => openSupport({ category: "SENHA" })}
          message={message}
        />
        {supportDialog}
      </>
    );
  }

  return (
    <div className={`appShell ${sidebarOpen ? "sidebarOpen" : "sidebarClosed"}`}>
      <aside className="appSidebar">
        <button
          type="button"
          className="mobileSidebarClose"
          onClick={() => setSidebarOpen(false)}
          aria-label="Fechar menu"
        >
          <XCircle size={22} />
        </button>
        <div className="sidebarBrand">
          <img src="/eduvigia-brand.png" alt="EduVigIA" />
        </div>
        <nav className="sidebarNav">
          {visibleMenu.map(([label, Icon, key]) => (
            <button
              key={key}
              type="button"
              className={`sidebarItem ${section === key ? "active" : ""}`}
              onClick={() => {
                navigate(key);
                if (window.innerWidth < 1050) setSidebarOpen(false);
              }}
            >
              <Icon size={21} />
              <span>{label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebarFooter">
          <strong>EduVigIA v2.0.0-F7-R3</strong>
          <span>Central operacional ativa</span>
          <span>Integração de vídeo preparada</span>
        </div>
      </aside>

      <main className="appMain">
        <header className="topbar">
          <button
            className="menuButton"
            type="button"
            aria-label={sidebarOpen ? "Recolher menu" : "Abrir menu"}
            onClick={() => setSidebarOpen((current) => !current)}
          >
            <Menu />
          </button>
          <div className="topSearch">
            <Search size={18} />
            <input
              value={globalSearch}
              onChange={(event) => setGlobalSearch(event.target.value)}
              placeholder="Buscar escola, câmera ou ocorrência"
            />
          </div>
          <div className="topActions">
            <button
              className="iconButton"
              type="button"
              onClick={() => setNotificationOpen((open) => !open)}
              aria-label="Notificações"
            >
              <Bell size={20} />
              {unreadCount > 0 && <i>{unreadCount > 99 ? "99+" : unreadCount}</i>}
            </button>
            <div className="profile">
              <CircleUserRound size={34} />
              <div>
                <strong>{authUser.name}</strong>
                <span>{roleLabel(authUser.role)} · {roleEnvironment(authUser.role)}</span>
              </div>
              <button className="logoutButton" type="button" onClick={logout}>Sair</button>
            </div>
          </div>
        </header>

        <ActionFeedbackBanner feedback={actionFeedback} onClose={clearActionFeedback} />

        {notificationOpen && (
          <div className="notificationDrawer">
            <div className="notificationHeader">
              <div>
                <h2>Notificações</h2>
                <span>{unreadCount} não lidas</span>
              </div>
              <button type="button" onClick={readAllNotifications}>Marcar todas como lidas</button>
            </div>
            <div className="notificationList">
              {notifications.length === 0 && <div className="emptyNotification">Nenhuma notificação.</div>}
              {notifications.map((item) => (
                <button
                  type="button"
                  key={item.id}
                  className={`notificationItem ${item.read_at ? "read" : "unread"} ${item.severity.toLowerCase()}`}
                  onClick={() => readNotification(item)}
                >
                  <div>
                    <b>{item.title}</b>
                    <span>{item.message}</span>
                  </div>
                  <small>{new Date(item.created_at).toLocaleString("pt-BR")}</small>
                </button>
              ))}
            </div>
          </div>
        )}

        <CameraFleetStatusContext.Provider value={cameraFleetStatus}>
          <div className="contentArea">
          {message && <div className="notice">{message}</div>}

          {section === "dashboard" && (
            <Dashboard
              dashboard={dashboard}
              alerts={alerts}
              onAlertAction={alertAction}
              onAlertOccurrence={alertToOccurrence}
              navigate={navigate}
              systemHealth={systemHealth}
            />
          )}

          {section === "operations" && can("alerts:view") && (
            <OperationalCenterPage
              onAlertAction={alertAction}
              onAlertOccurrence={alertToOccurrence}
              onOccurrenceDetails={openOccurrenceDetails}
              canOperate={can("alerts:operate")}
              onFeedback={showActionFeedback}
            />
          )}

          {section === "schools" && can("schools:view") && (
            <SchoolsPage
              schools={filteredSchools}
              form={schoolForm}
              setForm={setSchoolForm}
              onSubmit={saveSchool}
              onToggle={toggleSchool}
              onEdit={editSchool}
              onCancelEdit={cancelSchoolEdit}
              editingSchoolId={editingSchoolId}
              canWrite={can("schools:write")}
              onDetails={openSchoolDetails}
            />
          )}

          {section === "cameras" && can("cameras:view") && (
            <CamerasPage
              cameras={cameras}
              videoDevices={videoDevices}
              schools={schools}
              recorders={recorders}
              videoDeviceForm={videoDeviceForm}
              setVideoDeviceForm={setVideoDeviceForm}
              onVideoDeviceSubmit={createVideoDevice}
              onVideoDeviceDiscover={discoverVideoDevice}
              onVideoDeviceDelete={deleteVideoDevice}
              deviceDiscovery={deviceDiscovery}
              recorderForm={recorderForm}
              setRecorderForm={setRecorderForm}
              onRecorderSubmit={createRecorder}
              onRecorderTest={testRecorder}
              onRecorderTestChannels={testRecorderChannels}
              onRecorderReprovision={reprovisionRecorder}
              onRecorderEdit={editRecorder}
              onRecorderCancelEdit={resetRecorderForm}
              editingRecorderId={editingRecorderId}
              onRecorderDelete={deleteRecorder}
              onRecorderDiscover={discoverRecorder}
              recorderDiscovery={recorderDiscovery}
              selectedImportChannels={selectedImportChannels}
              setSelectedImportChannels={setSelectedImportChannels}
              updateExistingChannels={updateExistingChannels}
              setUpdateExistingChannels={setUpdateExistingChannels}
              onImportChannels={importDiscoveredChannels}
              onCloseDiscovery={() => {
                setRecorderDiscovery(null);
                setSelectedImportChannels([]);
                setUpdateExistingChannels(false);
              }}
              schoolName={schoolName}
              form={cameraForm}
              setForm={setCameraForm}
              onSubmit={createCamera}
              onEdit={editCamera}
              onCancelEdit={resetCameraForm}
              editingCameraId={editingCameraId}
              onTest={testCamera}
              onTestAll={testAllCameras}
              onDelete={deleteCamera}
              canWrite={can("cameras:write")}
              onProvision={provisionCamera}
              actionBusy={actionBusy}
            />
          )}

          {section === "camera-events" && can("events:view") && (
            <CameraEventsHealthPage
              events={cameraEvents}
              health={cameraHealth}
              recorderHealth={recorderHealth}
              overview={cameraEventOverview}
              schools={schools}
              cameras={cameras}
              recorders={recorders}
              canOperate={can("events:operate")}
              onRefresh={load}
              onFeedback={showActionFeedback}
            />
          )}

          {section === "monitor" && can("monitor:view") && (
            <MonitorPage
              cameras={cameras}
              schools={schools}
              alerts={alerts}
              occurrences={occurrences}
              onOpenOccurrence={openOccurrenceDetails}
              onSnapshot={snapshotOccurrence}
              onProvisionAll={async () => runBusyAction("monitor-provision-all", async () => {
                try {
                  const result = await api("/cameras/provision-all", { method: "POST" });
                  const detail = `${result.provisioned} stream(s) provisionado(s); ${result.failed} falha(s).`;
                  showActionFeedback(result.failed ? "error" : "success", result.failed ? "Publicação concluída com falhas" : "Streams publicados", detail);
                  await load();
                } catch (error) {
                  showActionFeedback("error", "Falha ao publicar streams", error.message || "Não foi possível provisionar os streams.");
                }
              })}
              canPtz={can("ptz:control")}
              userId={authUser?.id}
              onRefreshStatus={(cameraIds) => api("/monitoring/status-refresh", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ camera_ids: cameraIds }),
              })}
            />
          )}

          {section === "maps" && can("maps:view") && (
            <OperationalMapPage onNavigate={navigate} onFeedback={showActionFeedback} />
          )}

          {section === "floorplans" && can("floorplans:view") && (
            <FloorPlansPage
              schools={schools}
              cameras={cameras}
              canWrite={can("floorplans:write")}
              onNavigate={navigate}
            />
          )}

          {section === "video-wall" && can("wall:view") && (
            <VideoWallPage
              cameras={cameras}
              schools={schools}
              canWrite={can("wall:write")}
            />
          )}

          {section === "playback" && can("playback:view") && (
            <PlaybackPage
              cameras={cameras}
              schools={schools}
              occurrences={occurrences}
              canExport={can("evidence:export")}
            />
          )}

          {section === "alerts" && can("alerts:view") && (
            <AlertsPage
              alerts={alerts}
              schools={schools}
              cameras={cameras}
              onAlertAction={alertAction}
              onAlertOccurrence={alertToOccurrence}
              canOperate={can("alerts:operate")}
              onFeedback={showActionFeedback}
            />
          )}

          {section === "occurrences" && can("occurrences:view") && (
            <OccurrencesPage
              occurrences={occurrences}
              form={occurrenceForm}
              setForm={setOccurrenceForm}
              onSubmit={createOccurrence}
              onUpdate={updateOccurrence}
              teams={teams}
              canOperate={can("occurrences:operate")}
              onDetails={openOccurrenceDetails}
            />
          )}

          {section === "dispatch" && can("dispatch:view") && (
            <DispatchPage
              occurrences={occurrences}
              teams={teams}
              teamForm={teamForm}
              setTeamForm={setTeamForm}
              onCreateTeam={createTeam}
              onUpdate={updateOccurrence}
              onTeamStatus={updateTeamStatus}
              canOperate={can("dispatch:operate")}
            />
          )}

          {section === "equipment" && can("equipment:view") && (
            <EquipmentPage
              equipment={equipment}
              schools={schools}
              form={equipmentForm}
              setForm={setEquipmentForm}
              onSubmit={createEquipment}
              onDelete={deleteEquipment}
              onMaintenance={openMaintenance}
              canWrite={can("equipment:write")}
            />
          )}

          {section === "reports" && can("reports:view") && (
            <ReportsPage data={reportData} occurrences={occurrences} alerts={alerts} />
          )}

          {section === "audit" && can("audit:view") && (
            <AuditPage logs={auditLogs} />
          )}

          {section === "infrastructure" && (
            <InfrastructurePage onFeedback={showActionFeedback} />
          )}

          {section === "homologation" && (
            <HomologationPage
              data={homologationData}
              checklist={homologationChecklist}
              onRefresh={load}
              onFeedback={showActionFeedback}
            />
          )}

          {section === "security" && can("users:view") && (
            <SecurityPage />
          )}

          {section === "settings" && can("settings:view") && (
            <SettingsPage
              settings={settingsData}
              onSave={saveSetting}
              authUser={authUser}
              users={users}
              schools={schools}
              userForm={userForm}
              setUserForm={setUserForm}
              onCreateUser={createUser}
              onUpdateUser={updateUser}
              onResetPassword={resetUserPassword}
              passwordForm={passwordForm}
              setPasswordForm={setPasswordForm}
              onChangePassword={changePassword}
            />
          )}
          </div>
        </CameraFleetStatusContext.Provider>

        {supportDialog}

        {selectedSchool && (
          <DetailModal title={selectedSchool.school.name} onClose={() => setSelectedSchool(null)}>
            <div className="detailMetrics">
              <article><b>{selectedSchool.availability_percent}%</b><span>Disponibilidade</span></article>
              <article><b>{selectedSchool.cameras.length}</b><span>Câmeras</span></article>
              <article><b>{selectedSchool.equipment.length}</b><span>Equipamentos</span></article>
              <article><b>{selectedSchool.occurrences.length}</b><span>Ocorrências</span></article>
            </div>
            <h3>Câmeras</h3>
            {selectedSchool.cameras.map((camera) => (
              <div className="detailRow" key={camera.id}>
                <b>{camera.name}</b><span>{camera.location}</span><small>{camera.status}</small>
              </div>
            ))}
            <h3>Alertas recentes</h3>
            {selectedSchool.alerts.map((alert) => (
              <div className="detailRow" key={alert.id}>
                <b>{alert.event_type}</b><span>{alert.camera_name}</span><small>{alert.status}</small>
              </div>
            ))}
          </DetailModal>
        )}

        {selectedOccurrence && (
          <DetailModal title={selectedOccurrence.protocol} onClose={() => setSelectedOccurrence(null)}>
            <div className="occurrenceDetailHeader">
              <div><b>{selectedOccurrence.school_name}</b><span>{selectedOccurrence.description}</span></div>
              <span className="statusPill warning">{selectedOccurrence.status}</span>
            </div>
            <div className="detailActions">
              <button onClick={() => addOccurrenceNote(selectedOccurrence.id)}>Adicionar conclusão</button>
              <button onClick={() => window.open(`${API_URL}/occurrences/${selectedOccurrence.id}/print`, "_blank")}>Imprimir relatório</button>
            </div>
            <h3>Linha do tempo</h3>
            {(selectedOccurrence.events || []).map((event) => (
              <div className="timelineItem" key={event.id}>
                <b>{event.event_type}</b>
                <span>{event.description}</span>
                <small>{new Date(event.created_at).toLocaleString("pt-BR")} · {event.user_name}</small>
              </div>
            ))}
            <h3>Evidências</h3>
            {(selectedOccurrence.evidence || []).map((item) => (
              <div className="detailRow" key={item.id}>
                <b>{item.evidence_type}</b>
                <span>{item.original_name || item.filename}</span>
                <small>{item.created_by}</small>
              </div>
            ))}
          </DetailModal>
        )}
      </main>
    </div>
  );
}

function Dashboard({
  dashboard,
  alerts,
  onAlertAction,
  onAlertOccurrence,
  navigate,
  systemHealth,
}) {
  const cameraFleetStatus = useCameraFleetStatus();
  const cards = [
    ["Total de Escolas", dashboard.schools || 0, Building2, "navy"],
    ["Total de Câmeras", dashboard.cameras || 0, Camera, "cyan"],
    ["Câmeras Online", dashboard.online || 0, Video, "green"],
    ["Alertas Ativos", dashboard.alerts || 0, AlertTriangle, "amber"],
    ["Ocorrências Abertas", dashboard.occurrences || 0, Siren, "red"],
    ["Equipes em Atendimento", dashboard.teams || 0, Users, "teal"],
  ];

  return (
    <>
      <div className="pageHeading compact">
        <div>
          <h1>Olá! <span>Bem-vindo ao EduVigIA. Aqui está o resumo da segurança escolar.</span></h1>
        </div>
        <div className={`onlineStatus ${cameraFleetStatus.tone}`} title={cameraFleetStatus.detail}>
          {new Date().toLocaleString("pt-BR", {
            weekday: "long",
            day: "2-digit",
            month: "short",
            hour: "2-digit",
            minute: "2-digit",
          })}
          <b>{cameraFleetStatus.label}</b>
        </div>
      </div>

      <section className="metricGrid">
        {cards.map(([label, value, Icon, tone]) => (
          <article className="metricCard" key={label}>
            <span className={`metricIcon ${tone}`}>
              <Icon size={25} />
            </span>
            <div>
              <small>{label}</small>
              <strong>{value}</strong>
            </div>
          </article>
        ))}
      </section>

      <section className="operationsGrid">
        <div className="cameraWall">
          {CAMERA_TILES.map(([name, location], index) => (
            <div className="cameraTile" key={name}>
              <SecureStreamFrame testStream title={name} />
              <span className="cameraName">{name}</span>
              <span className="cameraLive">● LIVE</span>
              <small>{location}</small>
            </div>
          ))}
        </div>

        <div className="dashboardPanel alertsPanel">
          <div className="panelTitle">
            <h2>Alertas em Tempo Real</h2>
            <MoreHorizontal />
          </div>
          <div className="alertTable">
            <div className="alertHeader">
              <span>Ativo</span>
              <span>Prioridade</span>
              <span>Escola</span>
              <span>Ações</span>
            </div>
            {alerts.slice(0, 4).map((alert, index) => (
              <div className="alertRow" key={alert.id}>
                <div>
                  <b>{index + 1}. {alert.event_type}</b>
                  <small>{new Date(alert.created_at).toLocaleString("pt-BR")}</small>
                </div>
                <span className={`priority ${alert.priority.toLowerCase()}`}>
                  <i />
                  {priorityLabel(alert.priority)}
                </span>
                <span>
                  {alert.school_name}
                  <small>{alert.camera_name}</small>
                </span>
                <div className="rowActions">
                  <button onClick={() => navigate("monitor")}>VER</button>
                  <button onClick={() => onAlertAction(alert.id, "confirm")}>
                    CONFIRMAR
                  </button>
                  <button
                    className="dangerOutline"
                    onClick={() => onAlertAction(alert.id, "dismiss")}
                  >
                    DESCARTAR
                  </button>
                  <button
                    className="openOccurrence"
                    onClick={() => onAlertOccurrence(alert.id)}
                  >
                    OCORRÊNCIA
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="schoolMap">
          <div className="mapBlock green">Escola<br />João Silva</div>
          <div className="mapBlock yellow">Escola<br />Anísio Teixeira</div>
          <div className="mapBlock red">Escola<br />Darcy Ribeiro<small>OCORRÊNCIA</small></div>
          <div className="mapPattern" />
        </div>

        <div className="dashboardPanel systemHealth">
          <h2>Saúde do Sistema</h2>
          <div className="healthOverall">
            <span className={`statusPill ${systemHealth?.overall === "online" ? "success" : "warning"}`}>
              {systemHealth?.overall === "online" ? "OPERACIONAL" : "DEGRADADO"}
            </span>
            <small>{systemHealth?.checked_at ? new Date(systemHealth.checked_at).toLocaleString("pt-BR") : "Aguardando verificação"}</small>
          </div>
          <div className="healthServiceList">
            {Object.entries(systemHealth?.services || {}).map(([name, service]) => (
              <div key={name}>
                <span>{name.replaceAll("_", " ")}</span>
                <b className={service.status === "online" ? "serviceOnline" : "serviceOffline"}>
                  {service.status.toUpperCase()}
                </b>
              </div>
            ))}
            <div>
              <span>Câmeras offline</span>
              <b className={(systemHealth?.cameras?.offline || 0) > 0 ? "serviceOffline" : "serviceOnline"}>
                {systemHealth?.cameras?.offline || 0}
              </b>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}

function SchoolsPage({ schools, form, setForm, onSubmit, onToggle, onEdit, onCancelEdit, editingSchoolId, canWrite, onDetails }) {
  return (
    <Page title="Escolas" subtitle="Cadastro completo e situação operacional das unidades">
      <div className={`twoColumn wideForm ${!canWrite ? "singleColumn" : ""}`}>
        {canWrite && <form className="formCard" onSubmit={onSubmit}>
          <h2>{editingSchoolId ? "Editar escola" : "Nova escola"}</h2>
          <div className="formGrid">
            <Field label="Código da unidade">
              <input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} placeholder="ESC-001" />
            </Field>
            <Field label="Nome da unidade">
              <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </Field>
            <Field label="Endereço">
              <input required value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />
            </Field>
            <Field label="Bairro">
              <input value={form.neighborhood} onChange={(e) => setForm({ ...form, neighborhood: e.target.value })} />
            </Field>
            <Field label="Cidade">
              <input value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} />
            </Field>
            <Field label="Responsável">
              <input value={form.responsible} onChange={(e) => setForm({ ...form, responsible: e.target.value })} />
            </Field>
            <Field label="Telefone">
              <input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
            </Field>
            <Field label="E-mail">
              <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
            </Field>
            <Field label="Kit">
              <select value={form.kit_type} onChange={(e) => setForm({ ...form, kit_type: e.target.value })}>
                {Array.from({ length: 16 }, (_, index) => {
                  const number = index + 1;
                  const code = `KIT_${String(number).padStart(2, "0")}`;
                  return <option value={code} key={code}>Kit {String(number).padStart(2, "0")} — {number * 4} câmeras</option>;
                })}
              </select>
            </Field>
            <Field label="Situação operacional">
              <select value={form.operational_status} onChange={(e) => setForm({ ...form, operational_status: e.target.value })}>
                <option value="IMPLANTACAO">Implantação</option>
                <option value="OPERACIONAL">Operacional</option>
                <option value="MANUTENCAO">Manutenção</option>
                <option value="INATIVA">Inativa</option>
              </select>
            </Field>
            <Field label="Latitude">
              <input value={form.latitude} onChange={(e) => setForm({ ...form, latitude: e.target.value })} />
            </Field>
            <Field label="Longitude">
              <input value={form.longitude} onChange={(e) => setForm({ ...form, longitude: e.target.value })} />
            </Field>
          </div>
          <Field label="Observações">
            <textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
          </Field>
          <div className="formActions">
            <button className="primaryButton"><Plus size={18} />{editingSchoolId ? "Salvar alterações" : "Cadastrar escola"}</button>
            {editingSchoolId && <button type="button" onClick={onCancelEdit}>Cancelar edição</button>}
          </div>
        </form>}

        <div className="dataCard">
          <div className="cardHeader"><h2>Unidades cadastradas</h2><span>{schools.length}</span></div>
          <div className="records">
            {schools.length === 0 && <Empty text="Nenhuma escola cadastrada." />}
            {schools.map((school) => (
              <article className="record expandedRecord" key={school.id}>
                <span className="recordIcon"><Building2 /></span>
                <div>
                  <b>{school.name}</b>
                  <span>{school.code || "Sem código"} · {school.address}</span>
                  <small>{school.neighborhood || "Bairro não informado"} · {school.city || "Cidade não informada"}</small>
                  <small>{school.kit_type} · {school.responsible || "Sem responsável"} · {school.operational_status}</small>
                </div>
                <div className="recordActions">
                  <span className={`statusPill ${school.active ? "success" : "danger"}`}>{school.active ? "ATIVA" : "INATIVA"}</span>
                  <button type="button" onClick={() => onDetails(school.id)}>Detalhes</button>
                  {canWrite && <button type="button" onClick={() => onEdit(school)}>Editar</button>}
                  {canWrite && <button type="button" onClick={() => onToggle(school.id)}>{school.active ? "Inativar" : "Ativar"}</button>}
                </div>
              </article>
            ))}
          </div>
        </div>
      </div>
    </Page>
  );
}

function CamerasPage({
  cameras,
  schools,
  recorders = [],
  videoDevices = [],
  videoDeviceForm,
  setVideoDeviceForm,
  onVideoDeviceSubmit,
  onVideoDeviceDiscover,
  onVideoDeviceDelete,
  deviceDiscovery = {},
  recorderForm,
  setRecorderForm,
  onRecorderSubmit,
  onRecorderTest,
  onRecorderTestChannels,
  onRecorderReprovision,
  onRecorderEdit,
  onRecorderCancelEdit,
  editingRecorderId,
  onRecorderDelete,
  onRecorderDiscover,
  recorderDiscovery,
  selectedImportChannels,
  setSelectedImportChannels,
  updateExistingChannels,
  setUpdateExistingChannels,
  onImportChannels,
  onCloseDiscovery,
  schoolName,
  form,
  setForm,
  onSubmit,
  onEdit,
  onCancelEdit,
  editingCameraId,
  onTest,
  onTestAll,
  onDelete,
  canWrite,
  onProvision,
  actionBusy = {},
}) {
  const [tab, setTab] = useState("cameras");
  const activeRecorders = recorders.filter(
    (recorder) => !form.school_id || String(recorder.school_id) === String(form.school_id)
  );
  const selectedRecorder = recorders.find((recorder) => String(recorder.id) === String(form.recorder_id));
  const activeVideoDevices = videoDevices.filter((device) => !form.school_id || String(device.school_id) === String(form.school_id));
  const selectedVideoDevice = videoDevices.find((device) => String(device.id) === String(form.device_id));

  const previewSlug = (value) =>
    (value || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "");

  const selectedSchool = schools.find((school) => String(school.id) === String(form.school_id));
  const sourceCode = form.source_type === "NVR" ? `nvr-ch${String(form.nvr_channel || 1).padStart(2, "0")}` :
    form.source_type === "DVR" ? `dvr-ch${String(form.nvr_channel || 1).padStart(2, "0")}` : "cam";
  const basePreview = previewSlug(
    `${selectedSchool?.code || selectedSchool?.name || "escola"}-${sourceCode}-${form.location || form.name || "camera"}`
  );
  const channelNumber = form.device_id
    ? Number(form.logical_channel || 1)
    : (form.source_type === "NVR" || form.source_type === "DVR" ? Number(form.nvr_channel || 1) : 1);
  const mainChannel = channelNumber * 100 + 1;
  const subChannel = channelNumber * 100 + 2;

  return (
    <Page title="Câmeras e Gravadores" subtitle="Descoberta ISAPI, inventário, importação e testes MAIN/SUB">
      <div className="moduleTabs">
        <button type="button" className={tab === "cameras" ? "active" : ""} onClick={() => setTab("cameras")}>
          <Camera size={16} /> Câmeras e canais
        </button>
        <button type="button" className={tab === "recorders" ? "active" : ""} onClick={() => setTab("recorders")}>
          <Server size={16} /> Gravadores NVR/DVR
        </button>
        <button type="button" className={tab === "devices" ? "active" : ""} onClick={() => setTab("devices")}>
          <Camera size={16} /> Dispositivos multi-sensor
        </button>
      </div>

      {tab === "devices" && (
        <div className={`twoColumn wideForm ${!canWrite ? "singleColumn" : ""}`}>
          {canWrite && <form className="formCard" onSubmit={onVideoDeviceSubmit}>
            <h2>Novo dispositivo físico</h2>
            <p className="mutedText">Um IP e um conjunto de credenciais podem publicar vários sensores/canais.</p>
            <div className="formGrid">
              <Field label="Escola"><select required value={videoDeviceForm.school_id} onChange={(e)=>setVideoDeviceForm({...videoDeviceForm,school_id:e.target.value})}><option value="">Selecione</option>{schools.filter(x=>x.active).map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></Field>
              <Field label="Nome do equipamento"><input required value={videoDeviceForm.name} onChange={(e)=>setVideoDeviceForm({...videoDeviceForm,name:e.target.value})} placeholder="Térmica Portão Principal" /></Field>
              <Field label="Tipo"><select value={videoDeviceForm.device_type} onChange={(e)=>setVideoDeviceForm({...videoDeviceForm,device_type:e.target.value,channel_count:e.target.value==="BISPECTRUM"?2:videoDeviceForm.channel_count})}><option value="CAMERA">Câmera simples</option><option value="BISPECTRUM">Bi-spectrum (óptico + térmico)</option><option value="MULTISENSOR">Multi-sensor</option></select></Field>
              <Field label="IP"><input required value={videoDeviceForm.ip_address} onChange={(e)=>setVideoDeviceForm({...videoDeviceForm,ip_address:e.target.value})} /></Field>
              <Field label="Porta HTTP"><input type="number" value={videoDeviceForm.http_port} onChange={(e)=>setVideoDeviceForm({...videoDeviceForm,http_port:Number(e.target.value)})} /></Field>
              <Field label="Porta RTSP"><input type="number" value={videoDeviceForm.rtsp_port} onChange={(e)=>setVideoDeviceForm({...videoDeviceForm,rtsp_port:Number(e.target.value)})} /></Field>
              <Field label="Fabricante"><input value={videoDeviceForm.manufacturer} onChange={(e)=>setVideoDeviceForm({...videoDeviceForm,manufacturer:e.target.value})} /></Field>
              <Field label="Modelo"><input value={videoDeviceForm.model} onChange={(e)=>setVideoDeviceForm({...videoDeviceForm,model:e.target.value})} /></Field>
              <Field label="Quantidade de canais"><input type="number" min="1" max="32" value={videoDeviceForm.channel_count} onChange={(e)=>setVideoDeviceForm({...videoDeviceForm,channel_count:Number(e.target.value)})} /></Field>
              <Field label="Usuário técnico"><input value={videoDeviceForm.username} onChange={(e)=>setVideoDeviceForm({...videoDeviceForm,username:e.target.value})} /></Field>
              <Field label="Senha técnica"><input type="password" value={videoDeviceForm.password} onChange={(e)=>setVideoDeviceForm({...videoDeviceForm,password:e.target.value})} /></Field>
            </div>
            <button className="primaryButton"><Plus size={18}/>Cadastrar dispositivo</button>
          </form>}
          <div className="dataCard"><div className="cardHeader"><h2>Dispositivos físicos</h2><span>{videoDevices.length}</span></div><div className="records">
            {videoDevices.length===0 && <Empty text="Nenhum dispositivo multi-sensor cadastrado."/>}
            {videoDevices.map((device)=><article className="record expandedRecord" key={device.id}><span className="recordIcon"><Camera/></span><div><b>{device.name}</b><span>{schoolName(device.school_id)} · {device.device_type}</span><small>{device.ip_address} · RTSP {device.rtsp_port} · {device.channel_count} canal(is)</small>{deviceDiscovery[device.id]?.length>0 && <small>Detectados: {deviceDiscovery[device.id].map(c=>`CH${c.logical_channel} ${c.main?'MAIN':''}${c.sub?'/SUB':''}`).join(' · ')}</small>}</div><div className="recordActions"><span className={`statusPill ${device.status==="ONLINE"?"success":device.status==="OFFLINE"?"danger":"neutral"}`}>{device.status}</span>{canWrite&&<button type="button" onClick={()=>onVideoDeviceDiscover(device.id)}>Descobrir canais</button>}{canWrite&&<button type="button" className="dangerOutline" onClick={()=>onVideoDeviceDelete(device.id)}>Excluir</button>}</div></article>)}
          </div></div>
        </div>
      )}

      {tab === "recorders" && (
        <div className={`twoColumn wideForm ${!canWrite ? "singleColumn" : ""}`}>
          {canWrite && (
            <form className="formCard" onSubmit={onRecorderSubmit}>
              <h2>{editingRecorderId ? "Editar gravador" : "Novo gravador"}</h2>
              <div className="formGrid">
                <Field label="Escola">
                  <select required value={recorderForm.school_id} onChange={(e) => setRecorderForm({ ...recorderForm, school_id: e.target.value })}>
                    <option value="">Selecione</option>
                    {schools.filter((school) => school.active).map((school) => (
                      <option key={school.id} value={school.id}>{school.name}</option>
                    ))}
                  </select>
                </Field>
                <Field label="Nome do gravador">
                  <input required value={recorderForm.name} onChange={(e) => setRecorderForm({ ...recorderForm, name: e.target.value })} placeholder="NVR Principal" />
                </Field>
                <Field label="Fabricante">
                  <input value={recorderForm.manufacturer} onChange={(e) => setRecorderForm({ ...recorderForm, manufacturer: e.target.value })} />
                </Field>
                <Field label="Modelo">
                  <input value={recorderForm.model} onChange={(e) => setRecorderForm({ ...recorderForm, model: e.target.value })} />
                </Field>
                <Field label="Número de série">
                  <input value={recorderForm.serial_number} onChange={(e) => setRecorderForm({ ...recorderForm, serial_number: e.target.value })} />
                </Field>
                <Field label="Endereço IP">
                  <input required value={recorderForm.ip_address} onChange={(e) => setRecorderForm({ ...recorderForm, ip_address: e.target.value })} placeholder="192.168.10.200" />
                </Field>
                <Field label="Porta HTTP">
                  <input type="number" value={recorderForm.http_port} onChange={(e) => setRecorderForm({ ...recorderForm, http_port: Number(e.target.value) })} />
                </Field>
                <Field label="Porta HTTPS">
                  <input type="number" value={recorderForm.https_port} onChange={(e) => setRecorderForm({ ...recorderForm, https_port: Number(e.target.value) })} />
                </Field>
                <Field label="Porta RTSP">
                  <input type="number" value={recorderForm.rtsp_port} onChange={(e) => setRecorderForm({ ...recorderForm, rtsp_port: Number(e.target.value) })} />
                </Field>
                <Field label="Porta SDK">
                  <input type="number" value={recorderForm.sdk_port} onChange={(e) => setRecorderForm({ ...recorderForm, sdk_port: Number(e.target.value) })} />
                </Field>
                <Field label="Quantidade de canais">
                  <input type="number" min="1" max="256" value={recorderForm.channel_count} onChange={(e) => setRecorderForm({ ...recorderForm, channel_count: Number(e.target.value) })} />
                </Field>
                <Field label="Usuário de integração">
                  <input value={recorderForm.username} onChange={(e) => setRecorderForm({ ...recorderForm, username: e.target.value })} />
                </Field>
                <Field label="Senha de integração">
                  <input type="password" value={recorderForm.password} onChange={(e) => setRecorderForm({ ...recorderForm, password: e.target.value })} />
                </Field>
                <Field label="Firmware">
                  <input value={recorderForm.firmware} onChange={(e) => setRecorderForm({ ...recorderForm, firmware: e.target.value })} />
                </Field>
                <Field label="Data do firmware">
                  <input value={recorderForm.firmware_released_date || ""} onChange={(e) => setRecorderForm({ ...recorderForm, firmware_released_date: e.target.value })} />
                </Field>
                <Field label="Tipo detectado">
                  <input value={recorderForm.device_type || ""} onChange={(e) => setRecorderForm({ ...recorderForm, device_type: e.target.value })} />
                </Field>
                <Field label="Endereço MAC">
                  <input value={recorderForm.mac_address || ""} onChange={(e) => setRecorderForm({ ...recorderForm, mac_address: e.target.value })} />
                </Field>
              </div>
              <Field label="Observações">
                <textarea value={recorderForm.notes} onChange={(e) => setRecorderForm({ ...recorderForm, notes: e.target.value })} />
              </Field>
              <div className="formActions">
                <button className="primaryButton"><Plus size={18} />{editingRecorderId ? "Salvar alterações" : "Cadastrar gravador"}</button>
                {editingRecorderId && <button type="button" onClick={onRecorderCancelEdit}>Cancelar edição</button>}
              </div>
            </form>
          )}

          <div className="dataCard">
            <div className="cardHeader"><h2>Gravadores cadastrados</h2><span>{recorders.length}</span></div>
            <div className="records">
              {recorders.length === 0 && <Empty text="Nenhum gravador cadastrado." />}
              {recorders.map((recorder) => (
                <article className="record expandedRecord" key={recorder.id}>
                  <span className="recordIcon"><Server /></span>
                  <div>
                    <b>{recorder.name}</b>
                    <span>{schoolName(recorder.school_id)} · {recorder.manufacturer} {recorder.model || ""}</span>
                    <small>{recorder.ip_address} · HTTP {recorder.http_port} · RTSP {recorder.rtsp_port} · SDK {recorder.sdk_port}</small>
                    <small>{recorder.channel_count} canais · Descobertos {recorder.discovered_channel_count ?? "—"} · Firmware {recorder.firmware || "não informado"}</small>
                    <small>{recorder.device_type || "Tipo não identificado"}{recorder.mac_address ? ` · MAC ${recorder.mac_address}` : ""}</small>
                    {recorder.last_error && <small className="errorText">{recorder.last_error}</small>}
                  </div>
                  <div className="recordActions">
                    <span className={`statusPill ${recorder.status === "ONLINE" ? "success" : recorder.status === "OFFLINE" ? "danger" : recorder.status === "DEGRADADO" ? "warning" : "neutral"}`}>{recorder.status}</span>
                    {canWrite && <button type="button" onClick={() => onRecorderEdit(recorder)}>Editar</button>}
                    {canWrite && <button type="button" disabled={Boolean(actionBusy[`recorder-test-${recorder.id}`])} onClick={() => onRecorderTest(recorder.id)}>{actionBusy[`recorder-test-${recorder.id}`] ? "Testando..." : "Testar equipamento"}</button>}
                    {canWrite && <button type="button" onClick={() => onRecorderDiscover(recorder.id)}><Search size={14} />Descobrir canais</button>}
                    {canWrite && <button type="button" disabled={Boolean(actionBusy[`recorder-channels-${recorder.id}`])} onClick={() => onRecorderTestChannels(recorder.id)}>{actionBusy[`recorder-channels-${recorder.id}`] ? "Testando canais..." : "Testar canais"}</button>}
                    {canWrite && <button type="button" disabled={Boolean(actionBusy[`recorder-reprovision-${recorder.id}`])} onClick={() => onRecorderReprovision(recorder.id)}>{actionBusy[`recorder-reprovision-${recorder.id}`] ? "Publicando..." : "Reprovisionar"}</button>}
                    {canWrite && <button type="button" className="dangerOutline" onClick={() => onRecorderDelete(recorder.id)}><Trash2 size={14} />Excluir</button>}
                  </div>
                </article>
              ))}
            </div>
          </div>
        </div>
      )}

      {tab === "cameras" && (
        <div className={`twoColumn wideForm ${!canWrite ? "singleColumn" : ""}`}>
          {canWrite && <form className="formCard" onSubmit={onSubmit}>
            <h2>{editingCameraId ? "Editar câmera ou canal" : "Nova câmera ou canal"}</h2>
            <div className="formGrid">
              <Field label="Escola">
                <select required value={form.school_id} onChange={(e) => setForm({ ...form, school_id: e.target.value, recorder_id: "" })}>
                  <option value="">Selecione</option>
                  {schools.filter((school) => school.active).map((school) => (
                    <option key={school.id} value={school.id}>{school.name}</option>
                  ))}
                </select>
              </Field>

              <Field label="Origem do vídeo">
                <select value={form.source_type} onChange={(e) => setForm({ ...form, source_type: e.target.value, recorder_id: "", device_id: "" })}>
                  <option value="CAMERA_IP">Câmera IP direta</option>
                  <option value="NVR">Canal de NVR</option>
                  <option value="DVR">Canal de DVR</option>
                  <option value="RTSP_CUSTOM">RTSP personalizado</option>
                </select>
              </Field>

              {(form.source_type === "NVR" || form.source_type === "DVR") && (
                <>
                  <Field label="Gravador">
                    <select required value={form.recorder_id} onChange={(e) => setForm({ ...form, recorder_id: e.target.value })}>
                      <option value="">Selecione o gravador</option>
                      {activeRecorders.map((recorder) => (
                        <option key={recorder.id} value={recorder.id}>{recorder.name} · {recorder.ip_address}</option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Canal do gravador">
                    <input
                      required
                      type="number"
                      min="1"
                      max={selectedRecorder?.channel_count || 256}
                      value={form.nvr_channel}
                      onChange={(e) => setForm({ ...form, nvr_channel: Number(e.target.value) })}
                    />
                  </Field>
                </>
              )}

              <Field label="Nome da câmera">
                <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              </Field>
              <Field label="Localização">
                <input required value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} />
              </Field>

              {form.source_type === "CAMERA_IP" && (
                <>
                  <Field label="Equipamento físico compartilhado">
                    <select value={form.device_id || ""} onChange={(e)=>setForm({...form,device_id:e.target.value,ip_address:"",username:"",password:"",logical_channel:Number(form.logical_channel||1)})}>
                      <option value="">IP direto legado / câmera simples</option>
                      {activeVideoDevices.map((device)=><option key={device.id} value={device.id}>{device.name} · {device.ip_address} · {device.device_type}</option>)}
                    </select>
                  </Field>
                  {form.device_id ? <>
                    <Field label="Canal lógico"><input type="number" min="1" max={selectedVideoDevice?.channel_count||32} value={form.logical_channel||1} onChange={(e)=>setForm({...form,logical_channel:Number(e.target.value),ptz_channel:Number(e.target.value)})}/></Field>
                    <Field label="Tipo de sensor"><select value={form.sensor_type||"VISIBLE"} onChange={(e)=>setForm({...form,sensor_type:e.target.value,camera_type:e.target.value==="THERMAL"?"TERMICA":form.camera_type})}><option value="VISIBLE">Óptico / visível</option><option value="THERMAL">Térmico</option><option value="FUSION">Fusão</option><option value="GENERIC">Genérico</option></select></Field>
                    <Field label="Rótulo do sensor"><input value={form.sensor_label||""} onChange={(e)=>setForm({...form,sensor_label:e.target.value})} placeholder="Térmico / Óptico"/></Field>
                    <label className="checkField inlineCheckField"><input type="checkbox" checked={Boolean(form.primary_sensor)} onChange={(e)=>setForm({...form,primary_sensor:e.target.checked})}/>Sensor principal</label>
                  </> : <>
                    <Field label="Endereço IP"><input required value={form.ip_address} onChange={(e) => setForm({ ...form, ip_address: e.target.value })} placeholder="192.168.10.101" /></Field>
                    <Field label="Porta RTSP"><input type="number" value={form.port} onChange={(e) => setForm({ ...form, port: Number(e.target.value) })} /></Field>
                    <Field label="Usuário técnico"><input value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} /></Field>
                    <Field label="Senha técnica"><input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></Field>
                  </>}
                </>
              )}

              {form.source_type === "RTSP_CUSTOM" && (
                <>
                  <Field label="RTSP MAIN — alta qualidade">
                    <input required={!editingCameraId} value={form.rtsp_url_main || ""} onChange={(e) => setForm({ ...form, rtsp_url_main: e.target.value })} placeholder="rtsp://.../main" />
                  </Field>
                  <Field label="RTSP SUB — mosaico">
                    <input required={!editingCameraId} value={form.rtsp_url_sub || ""} onChange={(e) => setForm({ ...form, rtsp_url_sub: e.target.value })} placeholder="rtsp://.../sub" />
                  </Field>
                </>
              )}

              <Field label="Fabricante">
                <input value={form.manufacturer} onChange={(e) => setForm({ ...form, manufacturer: e.target.value })} />
              </Field>
              <Field label="Modelo">
                <input value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })} />
              </Field>
              <Field label="Tipo">
                <select value={form.camera_type} onChange={(e) => setForm({ ...form, camera_type: e.target.value, ptz_enabled: e.target.value === "PTZ" ? true : form.ptz_enabled })}>
                  <option value="FIXA">Fixa</option>
                  <option value="DOME">Dome</option>
                  <option value="BULLET">Bullet</option>
                  <option value="PTZ">PTZ</option>
                  <option value="TERMICA">Térmica</option>
                </select>
              </Field>
            </div>

            {form.camera_type === "PTZ" && (
              <section className="ptzConfigCard">
                <div className="ptzConfigHeader">
                  <div><b>PTZ — Controle operacional</b><span>Pan, tilt, zoom, STOP e presets via Hikvision ISAPI</span></div>
                  <label className="checkField">
                    <input type="checkbox" checked={Boolean(form.ptz_enabled)} onChange={(e) => setForm({ ...form, ptz_enabled: e.target.checked })} />
                    Habilitar PTZ
                  </label>
                </div>
                {form.ptz_enabled && (
                  <div className="formGrid compactProfileGrid">
                    <Field label="Protocolo PTZ">
                      <select value={form.ptz_protocol || "HIKVISION_ISAPI"} onChange={(e) => setForm({ ...form, ptz_protocol: e.target.value })}>
                        <option value="HIKVISION_ISAPI">Hikvision ISAPI</option>
                      </select>
                    </Field>
                    <Field label="Canal PTZ">
                      <input type="number" min="1" max="256" disabled={["NVR", "DVR"].includes(form.source_type)} value={["NVR", "DVR"].includes(form.source_type) ? (form.nvr_channel || 1) : (form.ptz_channel || 1)} onChange={(e) => setForm({ ...form, ptz_channel: Number(e.target.value) })} />
                    </Field>
                    {form.source_type === "CAMERA_IP" && (<>
                      <Field label="Porta de controle HTTP/HTTPS">
                        <input type="number" min="1" max="65535" value={form.ptz_http_port || 80} onChange={(e) => setForm({ ...form, ptz_http_port: Number(e.target.value) })} />
                      </Field>
                      <label className="checkField inlineCheckField">
                        <input type="checkbox" checked={Boolean(form.ptz_https)} onChange={(e) => setForm({ ...form, ptz_https: e.target.checked })} />
                        Usar HTTPS no ISAPI
                      </label>
                    </>)}
                  </div>
                )}
                <small>Em câmeras ligadas a NVR/DVR, o controle usa as credenciais e portas do gravador. Em dispositivo multi-sensor, usa as credenciais compartilhadas do equipamento físico. Em câmera IP direta legada, usa as credenciais da própria câmera.</small>
              </section>
            )}

            <div className="vmsProfileGrid">
              <section className="vmsProfileCard mainProfileCard">
                <div className="vmsProfileHeader">
                  <div><b>MAIN — Alta qualidade</b><span>Fullscreen, câmera única e investigação ao vivo</span></div>
                  <span className="qualityBadge">HQ</span>
                </div>
                <div className="formGrid compactProfileGrid">
                  <Field label="Codec MAIN">
                    <select value={form.main_codec || "H.264"} onChange={(e) => setForm({ ...form, main_codec: e.target.value })}>
                      <option value="H.264">H.264</option><option value="H.265">H.265</option>
                    </select>
                  </Field>
                  <Field label="Resolução MAIN">
                    <input value={form.main_resolution || ""} onChange={(e) => setForm({ ...form, main_resolution: e.target.value })} placeholder="1920x1080" />
                  </Field>
                  <Field label="FPS MAIN">
                    <input type="number" min="1" max="60" value={form.main_fps || 15} onChange={(e) => setForm({ ...form, main_fps: Number(e.target.value) })} />
                  </Field>
                  <Field label="Bitrate MAIN (kbps)">
                    <input type="number" min="64" value={form.main_bitrate_kbps || 4096} onChange={(e) => setForm({ ...form, main_bitrate_kbps: Number(e.target.value) })} />
                  </Field>
                </div>
              </section>

              <section className="vmsProfileCard subProfileCard">
                <div className="vmsProfileHeader">
                  <div><b>SUB — Mosaico</b><span>Grades 4/9/16 e economia de banda</span></div>
                  <span className="qualityBadge">ECO</span>
                </div>
                <div className="formGrid compactProfileGrid">
                  <Field label="Codec SUB">
                    <select value={form.sub_codec || "H.264"} onChange={(e) => setForm({ ...form, sub_codec: e.target.value })}>
                      <option value="H.264">H.264</option><option value="H.265">H.265</option>
                    </select>
                  </Field>
                  <Field label="Resolução SUB">
                    <input value={form.sub_resolution || ""} onChange={(e) => setForm({ ...form, sub_resolution: e.target.value })} placeholder="640x360" />
                  </Field>
                  <Field label="FPS SUB">
                    <input type="number" min="1" max="60" value={form.sub_fps || 10} onChange={(e) => setForm({ ...form, sub_fps: Number(e.target.value) })} />
                  </Field>
                  <Field label="Bitrate SUB (kbps)">
                    <input type="number" min="32" value={form.sub_bitrate_kbps || 512} onChange={(e) => setForm({ ...form, sub_bitrate_kbps: Number(e.target.value) })} />
                  </Field>
                </div>
              </section>
            </div>

            <div className="formGrid">
            </div>

            <div className="autoStreamBox">
              <b>Nomes gerados automaticamente</b>
              <span>Principal: <code>{basePreview || "selecione-escola-e-local"}-main</code></span>
              <span>Secundário: <code>{basePreview || "selecione-escola-e-local"}-sub</code></span>
              {(form.source_type === "NVR" || form.source_type === "DVR") && (
                <>
                  <span>Canal RTSP principal: <code>{mainChannel}</code></span>
                  <span>Canal RTSP secundário: <code>{subChannel}</code></span>
                </>
              )}
              <small>O backend remove acentos, evita duplicidade e acrescenta numeração quando necessário.</small>
            </div>

            <div className="checkRow">
              <label className="checkField">
                <input type="checkbox" checked={form.is_totem_camera} onChange={(e) => setForm({ ...form, is_totem_camera: e.target.checked })} />
                Câmera integrada ao totem
              </label>
            </div>
            <div className="formActions">
              <button className="primaryButton"><Plus size={18} />{editingCameraId ? "Salvar e reprovisionar" : "Cadastrar e provisionar"}</button>
              {editingCameraId && <button type="button" onClick={onCancelEdit}>Cancelar edição</button>}
            </div>
          </form>}

          <div className="dataCard">
            <div className="cardHeader">
              <h2>Câmeras e canais cadastrados</h2>
              <div className="headerActions">
                <span>{cameras.length}</span>
                {canWrite && cameras.length > 0 && <button type="button" disabled={Boolean(actionBusy["camera-test-all"])} onClick={onTestAll}>{actionBusy["camera-test-all"] ? "Testando câmeras..." : "Testar até 64 câmeras"}</button>}
              </div>
            </div>
            <div className="records">
              {cameras.length === 0 && <Empty text="Nenhuma câmera cadastrada." />}
              {cameras.map((camera) => {
                const recorder = recorders.find((item) => Number(item.id) === Number(camera.recorder_id));
                return (
                  <article className="record expandedRecord" key={camera.id}>
                    <span className="recordIcon"><Camera /></span>
                    <div>
                      <b>{camera.name}</b>
                      <span>{camera.code || "Código pendente"} · {schoolName(camera.school_id)} · {camera.location}{camera.device_id ? ` · CH${camera.logical_channel} · ${camera.sensor_type}` : ""}</span>
                      <small>
                        {camera.source_type === "NVR" || camera.source_type === "DVR"
                          ? `${camera.source_type} ${recorder?.name || ""} · canal ${camera.nvr_channel}`
                          : `${camera.manufacturer} ${camera.model || ""} · ${camera.ip_address || "IP do gravador"}:${camera.port || 554}`}
                      </small>
                      <small>MAIN: {camera.stream_name_main || "não gerado"} · {camera.main_status || "PENDING"} · {camera.main_codec || "—"} · {camera.main_resolution || "não detectada"} · {camera.main_fps || "—"} FPS</small>
                      <small>SUB: {camera.stream_name_sub || camera.stream_name || "não gerado"} · {camera.sub_status || "PENDING"} · {camera.sub_codec || camera.codec || "—"} · {camera.sub_resolution || camera.resolution || "não detectada"} · {camera.sub_fps || camera.fps || "—"} FPS</small>
                      {camera.ptz_enabled && <small className="ptzMetaLine">PTZ: habilitado · {camera.ptz_protocol || "HIKVISION_ISAPI"} · canal {camera.ptz_channel || camera.nvr_channel || 1}</small>}
                      {camera.last_check_at && <small>Último teste: {new Date(camera.last_check_at).toLocaleString("pt-BR")}</small>}
                      {camera.last_error && <small className="errorText">{camera.last_error}</small>}
                    </div>
                    <div className="recordActions">
                      <span className={`statusPill ${camera.status === "ONLINE" ? "success" : camera.status === "OFFLINE" ? "danger" : "neutral"}`}>{camera.status}</span>
                      {canWrite && <button type="button" onClick={() => onEdit(camera)}>Editar</button>}
                      {canWrite && <button type="button" disabled={Boolean(actionBusy[`camera-test-${camera.id}`])} onClick={() => onTest(camera.id)}>{actionBusy[`camera-test-${camera.id}`] ? "Testando..." : "Testar MAIN/SUB"}</button>}
                      {canWrite && <button type="button" disabled={Boolean(actionBusy[`camera-provision-${camera.id}`])} onClick={() => onProvision(camera.id)}>{actionBusy[`camera-provision-${camera.id}`] ? "Publicando..." : "Publicar streams"}</button>}
                      {canWrite && <button type="button" className="dangerOutline" onClick={() => onDelete(camera.id)}><Trash2 size={14} />Excluir</button>}
                    </div>
                  </article>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {recorderDiscovery && (
        <DetailModal title="Descoberta Hikvision / ISAPI" onClose={onCloseDiscovery}>
          <div className="discoverySummary">
            <div>
              <b>{recorderDiscovery.device?.device_name || "Gravador Hikvision"}</b>
              <span>Modelo: {recorderDiscovery.device?.model || "não informado"}</span>
              <span>Firmware: {recorderDiscovery.device?.firmware_version || "não informado"}</span>
              <span>Série: {recorderDiscovery.device?.serial_number || "não informada"}</span>
              <span>Tipo: {recorderDiscovery.device?.device_type || "não identificado"}</span>
              <span>MAC: {recorderDiscovery.device?.mac_address || "não informado"}</span>
            </div>
            <span className="statusPill success">{recorderDiscovery.channel_count} CANAIS</span>
          </div>

          <div className="discoveryChannels">
            {selectedImportChannels.map((channel, index) => (
              <article className="discoveryChannel" key={channel.channel}>
                <label className="checkField">
                  <input
                    type="checkbox"
                    checked={channel.selected}
                    onChange={(event) => {
                      const next = [...selectedImportChannels];
                      next[index] = { ...channel, selected: event.target.checked };
                      setSelectedImportChannels(next);
                    }}
                  />
                  {channel.configured ? "Atualizar" : "Importar"} canal {String(channel.channel).padStart(2, "0")}
                </label>
                <div className="channelDiscoveryStatus">
                  <span className={`statusPill ${channel.online ? "success" : "danger"}`}>{channel.online ? "ONLINE" : "OFFLINE"}</span>
                  {channel.configured && <span className="statusPill warning">JÁ CADASTRADO</span>}
                  {channel.ip_address && <small>IP detectado: {channel.ip_address}</small>}
                </div>
                <div className="formGrid">
                  <Field label="Nome">
                    <input
                      value={channel.name}
                      onChange={(event) => {
                        const next = [...selectedImportChannels];
                        next[index] = { ...channel, name: event.target.value };
                        setSelectedImportChannels(next);
                      }}
                    />
                  </Field>
                  <Field label="Localização">
                    <input
                      value={channel.location}
                      onChange={(event) => {
                        const next = [...selectedImportChannels];
                        next[index] = { ...channel, location: event.target.value };
                        setSelectedImportChannels(next);
                      }}
                    />
                  </Field>
                  <Field label="Tipo da câmera">
                    <select
                      value={channel.camera_type || "FIXA"}
                      onChange={(event) => {
                        const next = [...selectedImportChannels];
                        next[index] = { ...channel, camera_type: event.target.value };
                        setSelectedImportChannels(next);
                      }}
                    >
                      <option value="FIXA">Fixa</option>
                      <option value="DOME">Dome</option>
                      <option value="BULLET">Bullet</option>
                      <option value="PTZ">PTZ</option>
                      <option value="TERMICA">Térmica</option>
                    </select>
                  </Field>
                  <Field label="Codec">
                    <select
                      value={channel.codec || "H.264"}
                      onChange={(event) => {
                        const next = [...selectedImportChannels];
                        next[index] = { ...channel, codec: event.target.value };
                        setSelectedImportChannels(next);
                      }}
                    >
                      <option value="H.264">H.264</option>
                      <option value="H.265">H.265</option>
                      <option value="MJPEG">MJPEG</option>
                    </select>
                  </Field>
                  <Field label="Resolução SUB">
                    <input
                      value={channel.resolution}
                      onChange={(event) => {
                        const next = [...selectedImportChannels];
                        next[index] = { ...channel, resolution: event.target.value };
                        setSelectedImportChannels(next);
                      }}
                    />
                  </Field>
                  <Field label="FPS">
                    <input
                      type="number"
                      min="1"
                      max="30"
                      value={channel.fps}
                      onChange={(event) => {
                        const next = [...selectedImportChannels];
                        next[index] = { ...channel, fps: Number(event.target.value) };
                        setSelectedImportChannels(next);
                      }}
                    />
                  </Field>
                </div>
              </article>
            ))}
          </div>

          <label className="checkField updateExistingOption">
            <input
              type="checkbox"
              checked={updateExistingChannels}
              onChange={(event) => setUpdateExistingChannels(event.target.checked)}
            />
            Atualizar também os canais que já estão cadastrados
          </label>

          <div className="modalFooter">
            <button type="button" onClick={onCloseDiscovery}>Cancelar</button>
            <button type="button" className="primaryButton" onClick={onImportChannels}>
              <Plus size={16} /> Aplicar canais selecionados
            </button>
          </div>
        </DetailModal>
      )}
    </Page>
  );
}

function PTZControlPanel({ camera }) {
  const [status, setStatus] = useState(null);
  const [speed, setSpeed] = useState(4);
  const [message, setMessage] = useState("");
  const [presetNo, setPresetNo] = useState(1);
  const [presetName, setPresetName] = useState("Entrada principal");

  const refresh = async () => {
    try {
      const result = await api(`/cameras/${camera.id}/ptz/status`);
      setStatus(result);
    } catch (error) { setMessage(error.message); }
  };

  useEffect(() => { refresh(); }, [camera.id]);

  const acquire = async (force = false) => {
    try {
      const result = await api(`/cameras/${camera.id}/ptz/lease`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ force }),
      });
      setStatus((current) => ({ ...(current || {}), lease: result.lease }));
      setMessage("Controle PTZ assumido.");
    } catch (error) { setMessage(error.message); }
  };

  const release = async () => {
    try {
      await api(`/cameras/${camera.id}/ptz/lease`, { method: "DELETE" });
      setStatus((current) => ({ ...(current || {}), lease: { active: false, mine: false } }));
      setMessage("Controle PTZ liberado.");
    } catch (error) { setMessage(error.message); }
  };

  const move = async (direction) => {
    if (!status?.lease?.mine) return;
    try {
      await api(`/cameras/${camera.id}/ptz/move`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ direction, speed }),
      });
    } catch (error) { setMessage(error.message); }
  };

  const stop = async () => {
    if (!status?.lease?.mine) return;
    try { await api(`/cameras/${camera.id}/ptz/stop`, { method: "POST" }); }
    catch (error) { setMessage(error.message); }
  };

  const holdProps = (direction) => ({
    onPointerDown: (event) => { event.preventDefault(); move(direction); },
    onPointerUp: stop,
    onPointerCancel: stop,
    onPointerLeave: (event) => { if (event.buttons) stop(); },
  });

  const savePreset = async () => {
    try {
      await api(`/cameras/${camera.id}/ptz/presets`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ preset_no: Number(presetNo), name: presetName }),
      });
      setMessage(`Preset ${presetNo} salvo.`);
      await refresh();
    } catch (error) { setMessage(error.message); }
  };

  const gotoPreset = async (number) => {
    try {
      await api(`/cameras/${camera.id}/ptz/presets/${number}/goto`, { method: "POST" });
      setMessage(`Chamando preset ${number}.`);
    } catch (error) { setMessage(error.message); }
  };

  if (!camera.ptz_enabled) return null;
  return (
    <div className="ptzPanel" onContextMenu={(event) => event.preventDefault()}>
      <div className="ptzPanelHeader">
        <div><b>PTZ</b><small>{status?.protocol || camera.ptz_protocol || "HIKVISION_ISAPI"}</small></div>
        {!status?.lease?.mine ? (
          <button type="button" onClick={() => acquire(false)}>Assumir controle</button>
        ) : (
          <button type="button" onClick={release}>Liberar</button>
        )}
      </div>
      {status?.lease?.active && !status?.lease?.mine && <div className="ptzLeaseBusy">Em uso por {status.lease.holder}</div>}
      <div className="ptzControls">
        <div className="ptzPad">
          <button type="button" {...holdProps("UP_LEFT")}>↖</button>
          <button type="button" {...holdProps("UP")}>↑</button>
          <button type="button" {...holdProps("UP_RIGHT")}>↗</button>
          <button type="button" {...holdProps("LEFT")}>←</button>
          <button type="button" className="ptzStop" onClick={stop}>STOP</button>
          <button type="button" {...holdProps("RIGHT")}>→</button>
          <button type="button" {...holdProps("DOWN_LEFT")}>↙</button>
          <button type="button" {...holdProps("DOWN")}>↓</button>
          <button type="button" {...holdProps("DOWN_RIGHT")}>↘</button>
        </div>
        <div className="ptzZoom">
          <button type="button" {...holdProps("ZOOM_IN")}>Zoom +</button>
          <button type="button" {...holdProps("ZOOM_OUT")}>Zoom −</button>
          <label>Velocidade <b>{speed}</b></label>
          <input type="range" min="1" max="7" value={speed} onChange={(e) => setSpeed(Number(e.target.value))} />
        </div>
      </div>
      <div className="ptzPresetBox">
        <div className="ptzPresetCreate">
          <input type="number" min="1" max="256" value={presetNo} onChange={(e) => setPresetNo(Number(e.target.value))} />
          <input value={presetName} onChange={(e) => setPresetName(e.target.value)} placeholder="Nome do preset" />
          <button type="button" disabled={!status?.lease?.mine} onClick={savePreset}>Salvar posição</button>
        </div>
        <div className="ptzPresetList">
          {(status?.presets || []).map((preset) => (
            <button type="button" key={preset.preset_no} disabled={!status?.lease?.mine} onClick={() => gotoPreset(preset.preset_no)}>
              {preset.preset_no}. {preset.name}
            </button>
          ))}
        </div>
      </div>
      {message && <small className="ptzMessage">{message}</small>}
    </div>
  );
}

function CameraMonitorTile({
  camera,
  schoolName,
  qualityMode,
  gridSize,
  favorite,
  onToggleFavorite,
  runtimeStatus,
  activeOccurrence,
  onSnapshot,
  onOpenOccurrence,
  canPtz = false,
}) {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [tileNode, setTileNode] = useState(null);

  useEffect(() => {
    const onFullscreenChange = () => setIsFullscreen(document.fullscreenElement === tileNode);
    document.addEventListener("fullscreenchange", onFullscreenChange);
    return () => document.removeEventListener("fullscreenchange", onFullscreenChange);
  }, [tileNode]);

  const effectiveProfile = qualityMode === "MAIN"
    ? "MAIN"
    : qualityMode === "SUB"
      ? "SUB"
      : (isFullscreen || gridSize === 1 ? "MAIN" : "SUB");
  const effectiveStatus = runtimeStatus?.status || camera.status;

  const openFullscreen = async () => {
    if (!tileNode?.requestFullscreen) return;
    try { await tileNode.requestFullscreen(); } catch { /* navegador recusou fullscreen */ }
  };

  return (
    <div className="monitorTile advancedTile" ref={setTileNode}>
      {effectiveStatus === "ONLINE" ? (
        <SecureStreamFrame
          cameraId={camera.id}
          profile={effectiveProfile}
          title={`${camera.name} — ${effectiveProfile}`}
        />
      ) : (
        <div className="cameraUnavailable">
          <Camera size={44} />
          <b>{effectiveStatus === "OFFLINE" ? "Câmera offline" : "Stream pendente"}</b>
          <span>{runtimeStatus?.error || camera.last_error || "Aguardando conexão com o equipamento."}</span>
        </div>
      )}

      <div className="cameraOverlay">
        <div>
          <span>{camera.name} {camera.device_id && <em className={`sensorBadge sensor-${String(camera.sensor_type||"VISIBLE").toLowerCase()}`}>{camera.sensor_type === "THERMAL" ? "TÉRMICO" : camera.sensor_type === "VISIBLE" ? "VISÍVEL" : camera.sensor_type}</em>}</span>
          <small>{schoolName} · {camera.location}{camera.device_id ? ` · CH${camera.logical_channel}` : ""}</small>
        </div>
        <b className={effectiveStatus === "ONLINE" ? "liveText" : "offlineText"}>● {effectiveStatus}</b>
      </div>

      <div className="cameraTelemetry">
        <span>Qualidade: {qualityMode === "AUTO" ? `AUTO → ${effectiveProfile}` : effectiveProfile}</span>
        <span>{effectiveProfile === "MAIN" ? (camera.main_resolution || "MAIN") : (camera.sub_resolution || camera.resolution || "SUB")}</span>
        <span>Último status: {runtimeStatus?.checked_at ? new Date(runtimeStatus.checked_at).toLocaleTimeString("pt-BR") : camera.last_check_at ? new Date(camera.last_check_at).toLocaleString("pt-BR") : "não realizado"}</span>
      </div>

      <div className="cameraActions">
        <button type="button" onClick={openFullscreen}><Maximize2 size={14} /> Tela cheia</button>
        <button type="button" className={favorite ? "favoriteActive" : ""} onClick={() => onToggleFavorite(camera.id)}>
          {favorite ? "★ Favorita" : "☆ Favoritar"}
        </button>
        {activeOccurrence && <button type="button" onClick={() => onSnapshot(activeOccurrence.id, camera.id)}><FileImage size={14} /> Snapshot</button>}
        {activeOccurrence && <button type="button" onClick={() => onOpenOccurrence(activeOccurrence.id)}>Ocorrência</button>}
      </div>
      {canPtz && camera.ptz_enabled && <PTZControlPanel camera={camera} />}
    </div>
  );
}

function MonitorPage({
  cameras = [],
  videoDevices = [],
  schools = [],
  alerts = [],
  occurrences = [],
  onOpenOccurrence = () => {},
  onSnapshot = () => {},
  onProvisionAll = () => {},
  onRefreshStatus = async () => ({ cameras: [] }),
  canPtz = false,
  userId = null,
}) {
  const [view, setView] = useState("schools");
  const [selectedSchoolId, setSelectedSchoolId] = useState("");
  const monitorLayoutStorageKey = `eduvigia_monitor_layout_${userId || "default"}`;
  const [layoutMode, setLayoutMode] = useState(() => {
    try {
      const saved = localStorage.getItem(`eduvigia_monitor_layout_${userId || "default"}`);
      return ["AUTO", "1", "4", "6", "9", "16", "25", "36"].includes(saved) ? saved : "AUTO";
    } catch {
      return "AUTO";
    }
  });
  const [qualityMode, setQualityMode] = useState("AUTO");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [groupFilter, setGroupFilter] = useState("ALL");
  const [page, setPage] = useState(1);
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const [favorites, setFavorites] = useState([]);
  const [runtimeStatuses, setRuntimeStatuses] = useState({});

  useEffect(() => {
    try {
      const saved = localStorage.getItem(monitorLayoutStorageKey);
      setLayoutMode(["AUTO", "1", "4", "6", "9", "16", "25", "36"].includes(saved) ? saved : "AUTO");
    } catch {
      setLayoutMode("AUTO");
    }
  }, [monitorLayoutStorageKey]);

  useEffect(() => {
    try {
      localStorage.setItem(monitorLayoutStorageKey, layoutMode);
    } catch {
      // Preferência local indisponível; mantém a sessão atual.
    }
  }, [monitorLayoutStorageKey, layoutMode]);

  useEffect(() => {
    let cancelled = false;
    api("/monitoring/favorites")
      .then((result) => { if (!cancelled) setFavorites(result.camera_ids || []); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const schoolMap = useMemo(
    () => Object.fromEntries(schools.map((school) => [String(school.id), school])),
    [schools]
  );

  const schoolSummaries = useMemo(() => schools.map((school) => {
    const schoolCameras = cameras.filter((camera) => Number(camera.school_id) === Number(school.id));
    const online = schoolCameras.filter((camera) => camera.status === "ONLINE").length;
    const offline = schoolCameras.filter((camera) => camera.status === "OFFLINE").length;
    const pending = schoolCameras.length - online - offline;
    const schoolAlerts = alerts.filter(
      (alert) => alert.school_name === school.name && !["DESCARTADO", "ENCERRADO"].includes(alert.status)
    );
    const latestAlert = schoolAlerts
      .slice()
      .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))[0];
    return {
      ...school,
      total: schoolCameras.length,
      online,
      offline,
      pending,
      alerts: schoolAlerts.length,
      latestAlert,
      availability: schoolCameras.length ? Math.round((online / schoolCameras.length) * 100) : 0,
    };
  }), [schools, cameras, alerts]);

  const getGroup = (camera) => {
    if (camera.device_id && videoDevices.find((device) => Number(device.id) === Number(camera.device_id) && device.device_type !== "CAMERA")) return "MULTISENSOR";
    const text = `${camera.location || ""} ${camera.name || ""}`.toLowerCase();
    if (/port[aã]o|entrada|sa[ií]da|acesso/.test(text)) return "ACESSOS";
    if (/p[aá]tio|quadra|recreio/.test(text)) return "PATIO";
    if (/corredor|hall|escada/.test(text)) return "CIRCULACAO";
    if (/extern|estacionamento|per[ií]metro|muro/.test(text)) return "EXTERNA";
    if (/secretaria|dire[cç][aã]o|admin/.test(text)) return "ADMINISTRATIVA";
    return "OUTRAS";
  };

  const groups = [
    ["ALL", "Todos os setores"],
    ["MULTISENSOR", "Multi-sensor / térmica"],
    ["ACESSOS", "Entradas e saídas"],
    ["PATIO", "Pátio e recreação"],
    ["CIRCULACAO", "Corredores e circulação"],
    ["EXTERNA", "Área externa"],
    ["ADMINISTRATIVA", "Administrativa"],
    ["OUTRAS", "Outras áreas"],
  ];

  const selectedSchool = selectedSchoolId ? schoolMap[String(selectedSchoolId)] : null;
  const filteredCameras = cameras.filter((camera) => {
    const schoolMatch = !selectedSchoolId || String(camera.school_id) === String(selectedSchoolId);
    const statusMatch = statusFilter === "ALL" || camera.status === statusFilter;
    const groupMatch = groupFilter === "ALL" || getGroup(camera) === groupFilter;
    const favoriteMatch = !favoritesOnly || favorites.includes(camera.id);
    const text = `${camera.name} ${camera.location} ${schoolMap[String(camera.school_id)]?.name || ""}`.toLowerCase();
    const searchMatch = !search || text.includes(search.toLowerCase());
    return schoolMatch && statusMatch && groupMatch && favoriteMatch && searchMatch;
  });

  filteredCameras.sort((a,b) => {
    if (a.device_id && b.device_id && Number(a.device_id) === Number(b.device_id)) return Number(a.logical_channel||1)-Number(b.logical_channel||1);
    return Number(b.id)-Number(a.id);
  });

  const automaticGridSize = filteredCameras.length <= 1
    ? 1
    : filteredCameras.length <= 4
      ? 4
      : filteredCameras.length <= 6
        ? 6
        : filteredCameras.length <= 9
          ? 9
          : filteredCameras.length <= 16
            ? 16
            : filteredCameras.length <= 25
              ? 25
              : 36;
  const effectiveGridSize = layoutMode === "AUTO" ? automaticGridSize : Number(layoutMode);
  const totalPages = Math.max(1, Math.ceil(filteredCameras.length / effectiveGridSize));
  const safePage = Math.min(page, totalPages);
  const pageItems = filteredCameras.slice(
    (safePage - 1) * effectiveGridSize,
    safePage * effectiveGridSize
  );
  const gridLabel = effectiveGridSize === 1
    ? "1 × 1"
    : effectiveGridSize === 4
      ? "2 × 2"
      : effectiveGridSize === 6
        ? "3 × 2"
        : effectiveGridSize === 9
          ? "3 × 3"
          : effectiveGridSize === 16
            ? "4 × 4"
            : effectiveGridSize === 25
              ? "5 × 5"
              : "6 × 6";
  const activeOccurrences = occurrences.filter((item) => item.status !== "ENCERRADA");

  useEffect(() => {
    setPage(1);
  }, [selectedSchoolId, layoutMode, search, statusFilter, groupFilter, favoritesOnly]);

  const openSchool = (schoolId) => {
    setSelectedSchoolId(String(schoolId));
    setView("cameras");
    setPage(1);
  };

  const toggleFavorite = async (cameraId) => {
    const isFavorite = favorites.includes(cameraId);
    try {
      await api(`/monitoring/favorites/${cameraId}`, { method: isFavorite ? "DELETE" : "PUT" });
      setFavorites((current) => isFavorite ? current.filter((id) => id !== cameraId) : [...current, cameraId]);
    } catch {
      // Mantém a UI estável; a mensagem global tratará falhas de API em operações críticas.
    }
  };

  useEffect(() => {
    if (view !== "cameras" || pageItems.length === 0) return undefined;
    let cancelled = false;
    let timer = null;
    const refresh = async () => {
      try {
        const result = await onRefreshStatus(pageItems.map((camera) => camera.id));
        if (!cancelled) {
          setRuntimeStatuses((current) => {
            const next = { ...current };
            (result.cameras || []).forEach((item) => { next[item.camera_id] = item; });
            return next;
          });
        }
      } catch { /* mantém o último status conhecido */ }
      if (!cancelled) timer = window.setTimeout(refresh, 30000);
    };
    refresh();
    return () => { cancelled = true; if (timer) window.clearTimeout(timer); };
  }, [view, safePage, effectiveGridSize, selectedSchoolId, search, statusFilter, groupFilter, favoritesOnly, pageItems.map((item) => item.id).join(",")]);

  return (
    <Page
      title="Monitoramento Multi-escola"
      subtitle="Visão centralizada por escola, setor e câmera, com carregamento sob demanda"
    >
      <div className="monitorTopbar">
        <div className="monitorBreadcrumb">
          <button
            type="button"
            className={view === "schools" ? "active" : ""}
            onClick={() => {
              setView("schools");
              setSelectedSchoolId("");
            }}
          >
            Todas as escolas
          </button>
          {selectedSchool && (
            <>
              <span>›</span>
              <button type="button" className="active">{selectedSchool.name}</button>
            </>
          )}
        </div>
        <div className="monitorTopActions">
          <button type="button" onClick={onProvisionAll}>
            <RefreshCw size={15} /> Provisionar streams
          </button>
          <span className="statusPill success">VMS MAIN/SUB ATIVO</span>
        </div>
      </div>

      {view === "schools" && (
        <>
          <div className="monitorSummaryStrip">
            <div><b>{schools.length}</b><span>Escolas</span></div>
            <div><b>{cameras.length}</b><span>Câmeras</span></div>
            <div><b>{cameras.filter((item) => item.status === "ONLINE").length}</b><span>Online</span></div>
            <div><b>{cameras.filter((item) => item.status === "OFFLINE").length}</b><span>Offline</span></div>
            <div><b>{alerts.filter((item) => item.status !== "DESCARTADO").length}</b><span>Alertas ativos</span></div>
          </div>

          <div className="schoolMonitorGrid">
            {schoolSummaries.map((school) => (
              <article className="schoolMonitorCard" key={school.id}>
                <div className="schoolMonitorHeader">
                  <span className="schoolMonitorIcon"><Building2 size={24} /></span>
                  <div>
                    <h3>{school.name}</h3>
                    <small>{school.code || "Sem código"} · {school.city || "Cidade não informada"}</small>
                  </div>
                  <span className={`statusPill ${school.active ? "success" : "danger"}`}>
                    {school.active ? "ATIVA" : "INATIVA"}
                  </span>
                </div>

                <div className="schoolMonitorStats">
                  <div><b>{school.online}/{school.total}</b><span>Câmeras online</span></div>
                  <div><b>{school.alerts}</b><span>Alertas ativos</span></div>
                  <div><b>{school.availability}%</b><span>Disponibilidade</span></div>
                </div>

                <div className="availabilityTrack">
                  <span style={{ width: `${school.availability}%` }} />
                </div>

                <div className="schoolMonitorStatusLine">
                  <span className="onlineDot">{school.online} online</span>
                  <span className="offlineDot">{school.offline} offline</span>
                  <span className="pendingDot">{school.pending} pendentes</span>
                </div>

                <div className="schoolLatestEvent">
                  <b>Último evento</b>
                  <span>
                    {school.latestAlert
                      ? `${school.latestAlert.event_type} · ${new Date(school.latestAlert.created_at).toLocaleString("pt-BR")}`
                      : "Nenhum alerta ativo"}
                  </span>
                </div>

                <button type="button" className="primaryButton schoolOpenButton" onClick={() => openSchool(school.id)}>
                  <Video size={16} /> Abrir monitoramento
                </button>
              </article>
            ))}

            {schoolSummaries.length === 0 && (
              <div className="monitorEmpty">
                <Building2 size={36} />
                <b>Nenhuma escola cadastrada</b>
                <span>Cadastre uma escola e associe as câmeras para iniciar o monitoramento.</span>
              </div>
            )}
          </div>
        </>
      )}

      {view === "cameras" && (
        <>
          <div className="monitorToolbar multiSchoolToolbar">
            <select
              value={selectedSchoolId}
              onChange={(event) => {
                const value = event.target.value;
                setSelectedSchoolId(value);
                if (!value) setView("schools");
              }}
            >
              <option value="">Todas as escolas</option>
              {schools.map((school) => (
                <option key={school.id} value={school.id}>{school.name}</option>
              ))}
            </select>

            <input
              placeholder="Pesquisar câmera, local ou escola..."
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />

            <select value={groupFilter} onChange={(event) => setGroupFilter(event.target.value)}>
              {groups.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>

            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="ALL">Todos os status</option>
              <option value="ONLINE">Somente online</option>
              <option value="OFFLINE">Somente offline</option>
              <option value="PENDING">Somente pendentes</option>
            </select>

            <select
              value={layoutMode}
              onChange={(event) => setLayoutMode(event.target.value)}
              aria-label="Layout de monitoramento"
            >
              <option value="AUTO">Layout automático</option>
              <option value="1">1 câmera · 1 × 1</option>
              <option value="4">4 câmeras · 2 × 2</option>
              <option value="6">6 câmeras · 3 × 2</option>
              <option value="9">9 câmeras · 3 × 3</option>
              <option value="16">16 câmeras · 4 × 4</option>
              <option value="25">25 câmeras · 5 × 5</option>
              <option value="36">36 câmeras · 6 × 6</option>
            </select>

            <select value={qualityMode} onChange={(event) => setQualityMode(event.target.value)}>
              <option value="AUTO">Qualidade automática</option>
              <option value="SUB">Econômica (SUB)</option>
              <option value="MAIN">Alta (MAIN)</option>
            </select>

            <label className="checkField">
              <input
                type="checkbox"
                checked={favoritesOnly}
                onChange={(event) => setFavoritesOnly(event.target.checked)}
              />
              Favoritas
            </label>
          </div>

          <div className="cameraResultBar">
            <div>
              <b>{selectedSchool?.name || "Todas as escolas"}</b>
              <span>{filteredCameras.length} câmera(s) encontrada(s)</span>
            </div>
            <div className="cameraResultMeta">
              <span>{layoutMode === "AUTO" ? `Automático · ${gridLabel}` : `Manual · ${gridLabel}`}</span>
              <span>Página {safePage} de {totalPages}</span>
            </div>
          </div>

          {pageItems.length === 0 && (
            <div className="monitorEmpty">
              <Camera size={34} />
              <b>Nenhuma câmera encontrada</b>
              <span>Revise os filtros ou cadastre câmeras para esta escola.</span>
            </div>
          )}

          <div className={`monitorGrid grid-${effectiveGridSize}`}>
            {pageItems.map((camera) => (
              <CameraMonitorTile
                key={camera.id}
                camera={camera}
                schoolName={schoolMap[String(camera.school_id)]?.name || `Escola #${camera.school_id}`}
                qualityMode={qualityMode}
                gridSize={effectiveGridSize}
                favorite={favorites.includes(camera.id)}
                onToggleFavorite={toggleFavorite}
                runtimeStatus={runtimeStatuses[camera.id]}
                activeOccurrence={activeOccurrences[0]}
                onSnapshot={onSnapshot}
                onOpenOccurrence={onOpenOccurrence}
                canPtz={canPtz}
              />
            ))}
          </div>

          {totalPages > 1 && (
            <div className="monitorPagination">
              <button type="button" disabled={safePage <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>
                Anterior
              </button>
              <span>{safePage} / {totalPages}</span>
              <button type="button" disabled={safePage >= totalPages} onClick={() => setPage((value) => Math.min(totalPages, value + 1))}>
                Próxima
              </button>
            </div>
          )}
        </>
      )}
    </Page>
  );
}


function OperationalCenterPage({
  onAlertAction,
  onAlertOccurrence,
  onOccurrenceDetails,
  canOperate,
  onFeedback,
}) {
  const [data, setData] = useState({
    summary: {},
    alerts: [],
    occurrences: [],
    teams: [],
    recent_events: [],
  });
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [error, setError] = useState("");

  const loadOperations = async ({ userInitiated = false } = {}) => {
    setLoading(true);
    try {
      const result = await api("/operations/overview");
      setData(result);
      setLastUpdated(new Date());
      setError("");
      if (userInitiated) onFeedback?.("success", "Central operacional atualizada", "Dados operacionais sincronizados com sucesso.");
      return true;
    } catch (loadError) {
      setError(loadError.message);
      if (userInitiated) onFeedback?.("error", "Falha ao atualizar a Central Operacional", loadError.message || "Não foi possível atualizar os dados.");
      return false;
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadOperations();
  }, []);

  useEffect(() => {
    if (!autoRefresh) return undefined;
    const timer = window.setInterval(loadOperations, 10000);
    return () => window.clearInterval(timer);
  }, [autoRefresh]);

  const formatSla = (sla) => {
    if (!sla) return "Sem SLA";
    if (sla.status === "ESTOURADO") return `${Math.abs(sla.remaining_minutes)} min atrasado`;
    return `${Math.max(0, sla.remaining_minutes)} min restantes`;
  };

  const slaClass = (sla) => {
    if (!sla) return "neutral";
    if (sla.status === "ESTOURADO") return "danger";
    if (sla.status === "ATENCAO") return "warning";
    return "success";
  };

  const refreshAfter = async (callback) => {
    await callback();
    await loadOperations();
  };

  return (
    <Page
      title="Central Operacional"
      subtitle="Alertas, ocorrências, equipes e prazos operacionais em uma única visão"
    >
      <div className="operationsToolbar">
        <div>
          <span className="liveIndicator">● AO VIVO</span>
          <small>
            {lastUpdated
              ? `Atualizado às ${lastUpdated.toLocaleTimeString("pt-BR")}`
              : "Aguardando atualização"}
          </small>
        </div>
        <div className="operationsToolbarActions">
          <label className="checkField">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(event) => setAutoRefresh(event.target.checked)}
            />
            Atualização automática
          </label>
          <button type="button" onClick={() => loadOperations({ userInitiated: true })} disabled={loading}>
            <RefreshCw size={15} className={loading ? "spinIcon" : ""} /> {loading ? "Atualizando..." : "Atualizar agora"}
          </button>
        </div>
      </div>

      {error && <div className="operationsError">{error}</div>}
      {loading && (
        <div className="monitorEmpty">
          <RefreshCw size={30} />
          <b>Carregando central operacional...</b>
        </div>
      )}

      {!loading && (
        <>
          <div className="operationsKpis">
            <div className="operationKpi">
              <span>Alertas ativos</span>
              <b>{data.summary.active_alerts || 0}</b>
              <small>{data.summary.critical_alerts || 0} críticos</small>
            </div>
            <div className="operationKpi">
              <span>Ocorrências abertas</span>
              <b>{data.summary.open_occurrences || 0}</b>
              <small>Em acompanhamento</small>
            </div>
            <div className="operationKpi dangerKpi">
              <span>SLA estourado</span>
              <b>{data.summary.overdue_items || 0}</b>
              <small>Exigem atenção imediata</small>
            </div>
            <div className="operationKpi">
              <span>Equipes disponíveis</span>
              <b>{data.summary.available_teams || 0}</b>
              <small>de {data.summary.total_teams || 0} equipes</small>
            </div>
          </div>

          <div className="operationsGrid">
            <section className="operationsPanel">
              <div className="cardHeader">
                <h2>Alertas prioritários</h2>
                <span>{data.alerts.length}</span>
              </div>
              <div className="operationsList">
                {data.alerts.length === 0 && <Empty text="Nenhum alerta ativo." />}
                {data.alerts.map((alert) => (
                  <article className="operationItem" key={alert.id}>
                    <div className="operationItemHeader">
                      <b>{alert.event_type}</b>
                      <span className={`statusPill ${slaClass(alert.sla)}`}>
                        {formatSla(alert.sla)}
                      </span>
                    </div>
                    <span>{alert.school_name} · {alert.camera_name}</span>
                    <small>{new Date(alert.created_at).toLocaleString("pt-BR")} · {alert.status}</small>
                    {canOperate && (
                      <div className="operationActions">
                        <button type="button" onClick={() => refreshAfter(() => onAlertAction(alert.id, "analyze"))}>
                          Analisar
                        </button>
                        <button type="button" onClick={() => refreshAfter(() => onAlertAction(alert.id, "confirm"))}>
                          Confirmar
                        </button>
                        <button type="button" className="primaryButton" onClick={() => refreshAfter(() => onAlertOccurrence(alert.id))}>
                          Abrir ocorrência
                        </button>
                      </div>
                    )}
                  </article>
                ))}
              </div>
            </section>

            <section className="operationsPanel">
              <div className="cardHeader">
                <h2>Ocorrências em andamento</h2>
                <span>{data.occurrences.length}</span>
              </div>
              <div className="operationsList">
                {data.occurrences.length === 0 && <Empty text="Nenhuma ocorrência aberta." />}
                {data.occurrences.map((occurrence) => (
                  <article className="operationItem" key={occurrence.id}>
                    <div className="operationItemHeader">
                      <b>{occurrence.protocol}</b>
                      <span className={`statusPill ${slaClass(occurrence.sla)}`}>
                        {formatSla(occurrence.sla)}
                      </span>
                    </div>
                    <span>{occurrence.school_name} · {occurrence.category}</span>
                    <small>{occurrence.status} · Equipe: {occurrence.assigned_team || "não atribuída"}</small>
                    <div className="operationActions">
                      <button type="button" onClick={() => onOccurrenceDetails(occurrence.id)}>
                        Ver detalhes
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            </section>

            <section className="operationsPanel">
              <div className="cardHeader">
                <h2>Equipes</h2>
                <span>{data.teams.length}</span>
              </div>
              <div className="teamStatusGrid">
                {data.teams.length === 0 && <Empty text="Nenhuma equipe cadastrada." />}
                {data.teams.map((team) => (
                  <article className="teamStatusCard" key={team.id}>
                    <b>{team.name}</b>
                    <span>{team.team_type}</span>
                    <span className={`statusPill ${team.status === "DISPONIVEL" ? "success" : team.status === "INDISPONIVEL" ? "danger" : "warning"}`}>
                      {team.status}
                    </span>
                    <small>{team.phone || "Telefone não informado"}</small>
                  </article>
                ))}
              </div>
            </section>

            <section className="operationsPanel">
              <div className="cardHeader">
                <h2>Atividade recente</h2>
                <span>{data.recent_events.length}</span>
              </div>
              <div className="operationsTimeline">
                {data.recent_events.length === 0 && <Empty text="Nenhuma atividade recente." />}
                {data.recent_events.map((event) => (
                  <article key={event.id}>
                    <span className="timelineDot" />
                    <div>
                      <b>{event.event_type}</b>
                      <span>{event.description}</span>
                      <small>{new Date(event.created_at).toLocaleString("pt-BR")} · {event.user_name}</small>
                    </div>
                  </article>
                ))}
              </div>
            </section>
          </div>
        </>
      )}
    </Page>
  );
}



function CameraEventsHealthPage({
  events = [],
  health = [],
  recorderHealth = [],
  overview = {},
  schools = [],
  cameras = [],
  recorders = [],
  canOperate = false,
  onRefresh,
  onFeedback,
}) {
  const [filters, setFilters] = useState({
    school: "",
    camera: "",
    type: "",
    severity: "",
    state: "ALL",
  });
  const [testForm, setTestForm] = useState({
    camera_id: "",
    provider_event_type: "MOTION",
    event_state: "ACTIVE",
    severity: "",
  });
  const [busy, setBusy] = useState(false);
  const [healthBusy, setHealthBusy] = useState(false);
  const [localMessage, setLocalMessage] = useState("");

  const schoolMap = useMemo(
    () => Object.fromEntries(schools.map((school) => [String(school.id), school.name])),
    [schools]
  );
  const cameraMap = useMemo(
    () => Object.fromEntries(cameras.map((camera) => [String(camera.id), camera])),
    [cameras]
  );
  const recorderMap = useMemo(
    () => Object.fromEntries(recorders.map((recorder) => [String(recorder.id), recorder])),
    [recorders]
  );

  const eventTypes = useMemo(
    () => Array.from(new Set(events.map((item) => item.event_type).filter(Boolean))).sort(),
    [events]
  );

  const filteredEvents = useMemo(() => {
    return events.filter((item) => {
      if (filters.school && Number(item.school_id) !== Number(filters.school)) return false;
      if (filters.camera && Number(item.camera_id) !== Number(filters.camera)) return false;
      if (filters.type && item.event_type !== filters.type) return false;
      if (filters.severity && item.severity !== filters.severity) return false;
      if (filters.state === "ACTIVE" && !item.active) return false;
      if (filters.state === "INACTIVE" && item.active) return false;
      return true;
    });
  }, [events, filters]);

  const filteredHealth = useMemo(() => {
    return health.filter((item) => {
      if (filters.school && Number(item.school_id) !== Number(filters.school)) return false;
      if (filters.camera && Number(item.camera_id) !== Number(filters.camera)) return false;
      return true;
    });
  }, [health, filters.school, filters.camera]);

  const healthClass = (state) =>
    state === "ONLINE" ? "success" : state === "DEGRADADO" ? "warning" : state === "OFFLINE" ? "danger" : "neutral";

  const eventLabel = (type) =>
    ({
      CAMERA_ONLINE: "Câmera online",
      CAMERA_OFFLINE: "Câmera offline",
      VIDEO_LOSS: "Perda de vídeo",
      VIDEO_RESTORED: "Vídeo restabelecido",
      RTSP_FAILURE: "Falha RTSP",
      RTSP_RESTORED: "RTSP restabelecido",
      MOTION: "Movimento",
      TAMPER: "Sabotagem / obstrução",
      LINE_CROSSING: "Cruzamento de linha",
      INTRUSION: "Intrusão",
      REGION_ENTRANCE: "Entrada em região",
      REGION_EXIT: "Saída de região",
      OBJECT_LEFT: "Objeto abandonado",
      OBJECT_REMOVED: "Objeto removido",
      PEOPLE_COUNTING: "Contagem de pessoas",
      OCCUPANCY: "Ocupação",
      QUEUE: "Fila / permanência",
      AUDIO_ALARM: "Evento de áudio",
      DIGITAL_INPUT: "Entrada digital",
      RECORDING_FAILURE: "Falha de gravação",
      RECORDING_RESTORED: "Gravação restabelecida",
      STORAGE_FAILURE: "Falha de armazenamento",
      STORAGE_WARNING: "Alerta de armazenamento",
      NTP_DRIFT: "Desvio NTP",
      PTZ_FAULT: "Falha PTZ",
      RECORDER_OFFLINE: "Gravador offline",
      RECORDER_ONLINE: "Gravador online",
      DEVICE_REBOOT: "Reinicialização",
      UNKNOWN_DEVICE_EVENT: "Evento não catalogado",
    }[type] || type || "Evento");

  const refreshHealth = async () => {
    const cameraIds = cameras
      .filter((camera) => !filters.school || Number(camera.school_id) === Number(filters.school))
      .map((camera) => Number(camera.id))
      .filter(Boolean)
      .slice(0, 16);
    if (cameraIds.length === 0) {
      const detail = "Nenhuma câmera disponível para atualizar a saúde.";
      setLocalMessage(detail);
      onFeedback?.("error", "Saúde não atualizada", detail);
      return;
    }
    setHealthBusy(true);
    try {
      const result = await api("/camera-health/refresh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ camera_ids: cameraIds }),
      });
      const detail = `${result.online || 0} online, ${result.degraded || 0} degradada(s), ${result.offline || 0} offline. Nenhum evento automático foi gerado.`;
      setLocalMessage(`Saúde atualizada: ${detail}`);
      onFeedback?.("success", "Saúde das câmeras atualizada", detail);
      await onRefresh?.();
    } catch (error) {
      const detail = error.message || "Falha ao atualizar a saúde das câmeras.";
      setLocalMessage(detail);
      onFeedback?.("error", "Falha ao atualizar saúde", detail);
    } finally {
      setHealthBusy(false);
    }
  };

  const simulate = async (event) => {
    event.preventDefault();
    if (!testForm.camera_id) {
      const detail = "Selecione uma câmera para o teste controlado.";
      setLocalMessage(detail);
      onFeedback?.("error", "Teste não iniciado", detail);
      return;
    }
    setBusy(true);
    try {
      await api("/camera-events/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: "GENERIC",
          provider_event_type: testForm.provider_event_type,
          event_state: testForm.event_state,
          camera_id: Number(testForm.camera_id),
          severity: testForm.severity || null,
          metadata: { source: "browser_qa" },
        }),
      });
      const detail = "Evento de teste processado pelo motor de eventos.";
      setLocalMessage(detail);
      onFeedback?.("success", "Teste de evento concluído", detail);
      await onRefresh?.();
    } catch (error) {
      const detail = error.message || "Falha ao processar evento de teste.";
      setLocalMessage(detail);
      onFeedback?.("error", "Falha no teste de evento", detail);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Page
      title="Eventos & Saúde"
      subtitle="Eventos normalizados, telemetria e saúde operacional de câmeras e gravadores"
    >
      <div className="cameraEventKpis">
        <article><AlertTriangle size={20}/><span>Eventos ativos</span><b>{overview.active_events || 0}</b></article>
        <article><Siren size={20}/><span>Críticos</span><b>{overview.critical_events || 0}</b></article>
        <article><Camera size={20}/><span>Câmeras offline</span><b>{overview.offline_cameras || 0}</b></article>
        <article><Wrench size={20}/><span>Câmeras degradadas</span><b>{overview.degraded_cameras || 0}</b></article>
        <article><Server size={20}/><span>Gravadores offline</span><b>{overview.offline_recorders || 0}</b></article>
      </div>

      <div className="dataCard full">
        <div className="cardHeader">
          <div>
            <h2>Eventos recebidos</h2>
            <small>Deduplicação por dispositivo/canal/tipo com contador de repetição</small>
          </div>
          <button type="button" onClick={async () => {
            const ok = await onRefresh?.();
            onFeedback?.(ok === false ? "error" : "success", ok === false ? "Falha ao atualizar eventos" : "Eventos atualizados", ok === false ? "Não foi possível sincronizar os dados." : "Lista de eventos e saúde sincronizada.");
          }}><RefreshCw size={15}/> Atualizar</button>
        </div>

        <div className="cameraEventFilters">
          <select value={filters.school} onChange={(e) => setFilters({ ...filters, school: e.target.value, camera: "" })}>
            <option value="">Todas as escolas</option>
            {schools.map((school) => <option key={school.id} value={school.id}>{school.name}</option>)}
          </select>
          <select value={filters.camera} onChange={(e) => setFilters({ ...filters, camera: e.target.value })}>
            <option value="">Todas as câmeras</option>
            {cameras
              .filter((camera) => !filters.school || Number(camera.school_id) === Number(filters.school))
              .map((camera) => <option key={camera.id} value={camera.id}>{camera.code || `CAM-${camera.id}`} · {camera.name}</option>)}
          </select>
          <select value={filters.type} onChange={(e) => setFilters({ ...filters, type: e.target.value })}>
            <option value="">Todos os tipos</option>
            {eventTypes.map((type) => <option key={type} value={type}>{eventLabel(type)}</option>)}
          </select>
          <select value={filters.severity} onChange={(e) => setFilters({ ...filters, severity: e.target.value })}>
            <option value="">Todas as severidades</option>
            {["INFO","BAIXA","MEDIA","ALTA","CRITICA"].map((value) => <option key={value}>{value}</option>)}
          </select>
          <select value={filters.state} onChange={(e) => setFilters({ ...filters, state: e.target.value })}>
            <option value="ALL">Ativos e encerrados</option>
            <option value="ACTIVE">Somente ativos</option>
            <option value="INACTIVE">Somente encerrados</option>
          </select>
        </div>

        <div className="largeTable cameraEventTable">
          <div className="largeTableHeader">
            <span>Evento</span><span>Origem operacional</span><span>Severidade</span><span>Estado</span><span>Repetições</span><span>Último recebimento</span>
          </div>
          {filteredEvents.length === 0 && <Empty text="Nenhum evento de câmera encontrado." />}
          {filteredEvents.map((item) => {
            const camera = item.camera_id ? cameraMap[String(item.camera_id)] : null;
            const recorder = item.recorder_id ? recorderMap[String(item.recorder_id)] : null;
            return (
              <div className="largeTableRow" key={item.id}>
                <div><b>{eventLabel(item.event_type)}</b><small>{item.provider} · {item.provider_event_type}</small></div>
                <div><b>{camera?.name || recorder?.name || "Dispositivo"}</b><small>{schoolMap[String(item.school_id)] || `Escola #${item.school_id}`}{item.source_channel ? ` · CH${item.source_channel}` : ""}</small></div>
                <span className={`priority ${(item.severity || "BAIXA").toLowerCase()}`}><i />{item.severity}</span>
                <span className={`statusPill ${item.active ? "warning" : "success"}`}>{item.active ? "ATIVO" : "ENCERRADO"}</span>
                <b>{item.repeat_count || 1}</b>
                <small>{new Date(item.last_seen_at || item.occurred_at).toLocaleString("pt-BR")}</small>
              </div>
            );
          })}
        </div>
      </div>

      <div className="dataCard full">
        <div className="cardHeader">
          <div><h2>Saúde das câmeras</h2><small>RTSP, perfis de vídeo, gravação, armazenamento e telemetria disponível</small></div>
          <div className="cameraHealthActions">
            <span>{filteredHealth.length}</span>
            {canOperate && (
              <button type="button" onClick={refreshHealth} disabled={healthBusy}>
                <RefreshCw size={15} className={healthBusy ? "spinIcon" : ""}/>
                {healthBusy ? "Testando perfis..." : "Atualizar saúde"}
              </button>
            )}
          </div>
        </div>
        <div className="largeTable cameraHealthTable">
          <div className="largeTableHeader">
            <span>Câmera</span><span>Saúde</span><span>Vídeo</span><span>Gravação</span><span>Storage</span><span>Telemetria</span>
          </div>
          {filteredHealth.length === 0 && <Empty text="Nenhuma câmera disponível para o filtro." />}
          {filteredHealth.map((item) => {
            const camera = cameraMap[String(item.camera_id)];
            return (
              <div className="largeTableRow" key={item.camera_id}>
                <div><b>{camera?.code || `CAM-${item.camera_id}`} · {camera?.name || "Câmera"}</b><small>{schoolMap[String(item.school_id)] || `Escola #${item.school_id}`}</small></div>
                <span className={`statusPill ${healthClass(item.state)}`}>{item.state}</span>
                <div><b>RTSP {item.rtsp_online === true ? "OK" : item.rtsp_online === false ? "FALHA" : "N/D"}</b><small>MAIN {item.main_online === true ? "OK" : item.main_online === false ? "FALHA" : "N/D"} · SUB {item.sub_online === true ? "OK" : item.sub_online === false ? "FALHA" : "N/D"}</small></div>
                <span>{item.recording_status || "UNKNOWN"}</span>
                <span>{item.storage_status || "UNKNOWN"}</span>
                <div><b>{item.resolution || "N/D"} · {item.codec || "N/D"}</b><small>{item.fps ?? "N/D"} FPS · {item.bitrate_kbps ?? "N/D"} kbps{item.ntp_offset_ms !== null && item.ntp_offset_ms !== undefined ? ` · NTP ${item.ntp_offset_ms} ms` : ""}</small></div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="dataCard full">
        <div className="cardHeader">
          <div><h2>Saúde dos gravadores</h2><small>Disponibilidade e estado operacional consolidado do NVR/DVR</small></div>
          <span>{recorderHealth.length}</span>
        </div>
        <div className="cameraRecorderHealthGrid">
          {recorderHealth.length === 0 && <Empty text="Nenhum gravador cadastrado." />}
          {recorderHealth.map((item) => {
            const recorder = recorderMap[String(item.recorder_id)];
            return (
              <article key={item.recorder_id}>
                <div><Server size={18}/><b>{recorder?.name || `Gravador #${item.recorder_id}`}</b></div>
                <span className={`statusPill ${healthClass(item.state)}`}>{item.state}</span>
                <small>Gravação: {item.recording_status || "UNKNOWN"} · Storage: {item.storage_status || "UNKNOWN"}</small>
                <small>Último contato: {item.last_seen_at ? new Date(item.last_seen_at).toLocaleString("pt-BR") : "N/D"}</small>
                {item.last_error && <small className="dangerText">{item.last_error}</small>}
              </article>
            );
          })}
        </div>
      </div>

      {canOperate && (
        <form className="dataCard full cameraEventTestForm" onSubmit={simulate}>
          <div className="cardHeader">
            <div><h2>Teste controlado do motor de eventos</h2><small>Somente para homologação; não substitui teste com equipamento real.</small></div>
            <span>QA</span>
          </div>
          <div className="formGrid">
            <Field label="Câmera">
              <select required value={testForm.camera_id} onChange={(e) => setTestForm({ ...testForm, camera_id: e.target.value })}>
                <option value="">Selecione</option>
                {cameras.map((camera) => <option key={camera.id} value={camera.id}>{camera.code || `CAM-${camera.id}`} · {camera.name}</option>)}
              </select>
            </Field>
            <Field label="Evento">
              <select value={testForm.provider_event_type} onChange={(e) => setTestForm({ ...testForm, provider_event_type: e.target.value })}>
                {["MOTION","TAMPER","LINE_CROSSING","INTRUSION","VIDEO_LOSS","RECORDING_FAILURE","STORAGE_FAILURE","DIGITAL_INPUT"].map((value) => <option key={value}>{value}</option>)}
              </select>
            </Field>
            <Field label="Estado">
              <select value={testForm.event_state} onChange={(e) => setTestForm({ ...testForm, event_state: e.target.value })}>
                <option value="ACTIVE">ACTIVE</option>
                <option value="INACTIVE">INACTIVE / recuperação</option>
              </select>
            </Field>
            <Field label="Severidade opcional">
              <select value={testForm.severity} onChange={(e) => setTestForm({ ...testForm, severity: e.target.value })}>
                <option value="">Automática</option>
                {["INFO","BAIXA","MEDIA","ALTA","CRITICA"].map((value) => <option key={value}>{value}</option>)}
              </select>
            </Field>
          </div>
          <button className="primaryButton" type="submit" disabled={busy}><Siren size={16}/>{busy ? "Processando..." : "Gerar evento de teste"}</button>
          {localMessage && <small className="formMessage">{localMessage}</small>}
        </form>
      )}
    </Page>
  );
}

function AlertsPage({ alerts: initialAlerts, schools = [], cameras = [], onAlertAction, onAlertOccurrence, canOperate, onFeedback }) {
  const [items, setItems] = useState(initialAlerts || []);
  const [overview, setOverview] = useState({ summary: {}, by_priority: {} });
  const [filters, setFilters] = useState({ search: "", status: "", priority: "" });
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [soundEnabled, setSoundEnabled] = useState(false);
  const [lastKnownId, setLastKnownId] = useState(0);
  const [evidenceUrl, setEvidenceUrl] = useState("");
  const [assignmentName, setAssignmentName] = useState("");
  const [alertForm, setAlertForm] = useState({ school_id: "", camera_id: "", event_type: "", priority: "MEDIA", summary: "" });

  useEffect(() => {
    setItems(initialAlerts || []);
  }, [initialAlerts]);

  const playAlertSound = () => {
    if (!soundEnabled) return;
    try {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      const context = new AudioContextClass();
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      oscillator.type = "sine";
      oscillator.frequency.setValueAtTime(880, context.currentTime);
      gain.gain.setValueAtTime(0.0001, context.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.16, context.currentTime + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, context.currentTime + 0.35);
      oscillator.connect(gain);
      gain.connect(context.destination);
      oscillator.start();
      oscillator.stop(context.currentTime + 0.38);
    } catch {
      // O navegador pode bloquear áudio antes da primeira interação do usuário.
    }
  };

  const loadAlerts = async ({ notifyNew = false, userInitiated = false } = {}) => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filters.search) params.set("search", filters.search);
      if (filters.status) params.set("status", filters.status);
      if (filters.priority) params.set("priority", filters.priority);
      params.set("limit", "300");
      const [rows, summary] = await Promise.all([
        api(`/alerts?${params.toString()}`),
        api("/alerts/overview"),
      ]);
      const newestId = rows.reduce((maximum, item) => Math.max(maximum, Number(item.id) || 0), 0);
      if (notifyNew && lastKnownId && newestId > lastKnownId && rows.some((item) => Number(item.id) > lastKnownId && item.status === "NOVO")) {
        playAlertSound();
      }
      setLastKnownId((current) => Math.max(current, newestId));
      setItems(rows);
      setOverview(summary);
      setMessage("");
      if (userInitiated) onFeedback?.("success", "Central de Alertas atualizada", `${rows.length} alerta(s) carregado(s).`);
      return true;
    } catch (error) {
      setMessage(error.message);
      if (userInitiated) onFeedback?.("error", "Falha ao atualizar alertas", error.message || "Não foi possível carregar a fila operacional.");
      return false;
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAlerts();
  }, [filters.status, filters.priority]);

  useEffect(() => {
    const timer = window.setInterval(() => loadAlerts({ notifyNew: true }), 7000);
    return () => window.clearInterval(timer);
  }, [filters, soundEnabled, lastKnownId]);

  useEffect(() => () => {
    if (evidenceUrl) URL.revokeObjectURL(evidenceUrl);
  }, [evidenceUrl]);

  const openDetails = async (id) => {
    try {
      setEvidenceUrl((current) => {
        if (current) URL.revokeObjectURL(current);
        return "";
      });
      const detail = await api(`/alerts/${id}/details`);
      setSelected(detail);
      setAssignmentName(detail.assigned_user_name || "");
      if (detail.has_evidence) {
        const token = localStorage.getItem("eduvigia_token");
        const response = await fetch(`${API_URL}/alerts/${id}/evidence`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (response.ok) {
          const blob = await response.blob();
          setEvidenceUrl(URL.createObjectURL(blob));
        }
      }
    } catch (error) {
      setMessage(error.message);
    }
  };

  const applyAction = async (id, action) => {
    try {
      await onAlertAction(id, action);
      await loadAlerts();
      if (selected?.id === id) await openDetails(id);
    } catch (error) {
      setMessage(error.message);
    }
  };

  const assignAlert = async () => {
    if (!selected) return;
    try {
      await api(`/alerts/${selected.id}/assign`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ assigned_user_name: assignmentName || null }),
      });
      await openDetails(selected.id);
      await loadAlerts();
      setMessage("Responsável atualizado.");
    } catch (error) {
      setMessage(error.message);
    }
  };

  const createManualAlert = async (event) => {
    event.preventDefault();
    try {
      await api("/alerts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          school_id: Number(alertForm.school_id),
          camera_id: alertForm.camera_id ? Number(alertForm.camera_id) : null,
          event_type: alertForm.event_type,
          priority: alertForm.priority,
          summary: alertForm.summary || null,
        }),
      });
      setAlertForm({ school_id: "", camera_id: "", event_type: "", priority: "MEDIA", summary: "" });
      await loadAlerts();
      setMessage("Alerta operacional criado com sucesso.");
    } catch (error) {
      setMessage(error.message);
    }
  };

  const alertCameras = alertForm.school_id
    ? cameras.filter((camera) => Number(camera.school_id) === Number(alertForm.school_id))
    : [];

  const summary = overview.summary || {};
  const priority = overview.by_priority || {};

  return (
    <Page title="Central de Alertas" subtitle="Triagem em tempo real, evidências, vídeo ao vivo e despacho operacional">
      <div className="alertCenterHero">
        <div>
          <span className="liveIndicator">● MONITORAMENTO ATIVO</span>
          <h2>Fila operacional de segurança</h2>
          <p>Eventos manuais e eventos dos módulos da plataforma são tratados como alertas rastreáveis, com evidência e histórico de atendimento.</p>
        </div>
        <div className="alertCenterHeroActions">
          <button type="button" className={soundEnabled ? "primaryButton" : "secondaryButton"} onClick={() => { setSoundEnabled((value) => !value); if (!soundEnabled) playAlertSound(); }}>
            <Bell size={16} /> {soundEnabled ? "Som ativado" : "Ativar som"}
          </button>
          <button type="button" onClick={() => loadAlerts({ userInitiated: true })} disabled={loading}>
            <RefreshCw size={16} className={loading ? "spinIcon" : ""} /> {loading ? "Atualizando..." : "Atualizar"}
          </button>
        </div>
      </div>

      {message && <div className="operationsError">{message}</div>}

      {canOperate && (
        <form className="dataCard alertManualForm" onSubmit={createManualAlert}>
          <div className="cardHeader"><h2>Novo alerta operacional</h2><span>Manual</span></div>
          <div className="formGrid">
            <Field label="Escola">
              <select required value={alertForm.school_id} onChange={(event) => setAlertForm({ ...alertForm, school_id: event.target.value, camera_id: "" })}>
                <option value="">Selecione</option>
                {schools.filter((school) => school.active).map((school) => <option key={school.id} value={school.id}>{school.name}</option>)}
              </select>
            </Field>
            <Field label="Câmera (opcional)">
              <select value={alertForm.camera_id} onChange={(event) => setAlertForm({ ...alertForm, camera_id: event.target.value })}>
                <option value="">Sem câmera vinculada</option>
                {alertCameras.map((camera) => <option key={camera.id} value={camera.id}>{camera.code || `CAM-${camera.id}`} · {camera.name}</option>)}
              </select>
            </Field>
            <Field label="Evento">
              <input required minLength={3} maxLength={120} value={alertForm.event_type} onChange={(event) => setAlertForm({ ...alertForm, event_type: event.target.value })} placeholder="Ex.: Acesso não autorizado" />
            </Field>
            <Field label="Prioridade">
              <select value={alertForm.priority} onChange={(event) => setAlertForm({ ...alertForm, priority: event.target.value })}>
                <option value="BAIXA">Baixa</option><option value="MEDIA">Média</option><option value="ALTA">Alta</option><option value="CRITICA">Crítica</option>
              </select>
            </Field>
          </div>
          <Field label="Resumo">
            <textarea maxLength={500} value={alertForm.summary} onChange={(event) => setAlertForm({ ...alertForm, summary: event.target.value })} placeholder="Contexto operacional do alerta" />
          </Field>
          <button className="primaryButton" type="submit"><Plus size={16} />Criar alerta</button>
        </form>
      )}

      <div className="alertCenterKpis">
        <article><span>Novos</span><b>{summary.new || 0}</b><small>Aguardando triagem</small></article>
        <article><span>Em atendimento</span><b>{summary.in_service || 0}</b><small>Com operador</small></article>
        <article className="critical"><span>Críticos</span><b>{summary.critical || 0}</b><small>Prioridade imediata</small></article>
        <article><span>Com evidência</span><b>{summary.with_evidence || 0}</b><small>Imagem protegida</small></article>
        <article><span>Últimas 24h</span><b>{summary.last_24h || 0}</b><small>Total recebido</small></article>
      </div>

      <div className="alertPriorityStrip">
        <span>Crítica <b>{priority.CRITICA || 0}</b></span>
        <span>Alta <b>{priority.ALTA || 0}</b></span>
        <span>Média <b>{priority.MEDIA || 0}</b></span>
        <span>Baixa <b>{priority.BAIXA || 0}</b></span>
      </div>

      <div className="alertFilters">
        <div className="searchBox">
          <Search size={16} />
          <input
            placeholder="Pesquisar evento, escola, câmera ou resumo..."
            value={filters.search}
            onChange={(event) => setFilters({ ...filters, search: event.target.value })}
            onKeyDown={(event) => event.key === "Enter" && loadAlerts()}
          />
        </div>
        <select value={filters.status} onChange={(event) => setFilters({ ...filters, status: event.target.value })}>
          <option value="">Todos os status</option>
          <option value="NOVO">Novo</option>
          <option value="EM_ATENDIMENTO">Em atendimento</option>
          <option value="CONFIRMADO">Confirmado</option>
          <option value="DESCARTADO">Descartado</option>
          <option value="ENCERRADO">Encerrado</option>
        </select>
        <select value={filters.priority} onChange={(event) => setFilters({ ...filters, priority: event.target.value })}>
          <option value="">Todas as prioridades</option>
          <option value="CRITICA">Crítica</option>
          <option value="ALTA">Alta</option>
          <option value="MEDIA">Média</option>
          <option value="BAIXA">Baixa</option>
        </select>
        <button type="button" onClick={() => loadAlerts()}><Search size={15} /> Filtrar</button>
      </div>

      <div className="dataCard full alertCenterTableCard">
        <div className="cardHeader"><h2>Alertas em tempo real</h2><span>{items.length}</span></div>
        <div className="largeTable alertCenterTable">
          <div className="largeTableHead">
            <span>Evento</span><span>Prioridade</span><span>Escola / Câmera</span><span>Responsável</span><span>Status</span><span>Ações</span>
          </div>
          {items.length === 0 && <Empty text="Nenhum alerta encontrado para os filtros selecionados." />}
          {items.map((alert) => (
            <div className={`largeTableRow alertRow ${alert.status === "NOVO" ? "newAlertRow" : ""}`} key={alert.id}>
              <div>
                <b>{alert.event_type}</b>
                <small>{alert.summary || new Date(alert.created_at).toLocaleString("pt-BR")}</small>
                <small>{new Date(alert.event_occurred_at || alert.created_at).toLocaleString("pt-BR")}</small>
              </div>
              <span className={`priority ${alert.priority.toLowerCase()}`}><i />{priorityLabel(alert.priority)}</span>
              <div><b>{alert.school_name}</b><small>{alert.camera_name}</small></div>
              <div><b>{alert.assigned_user_name || "Não atribuído"}</b><small>Atendimento operacional</small></div>
              <div><span className={`statusPill ${alert.status === "NOVO" ? "warning" : alert.status === "DESCARTADO" ? "neutral" : alert.status === "ENCERRADO" ? "success" : "info"}`}>{alert.status.replaceAll("_", " ")}</span><small>{alert.assigned_user_name || "Sem responsável"}</small></div>
              <div className="rowActions alertRowActions">
                <button type="button" onClick={() => openDetails(alert.id)}><Eye size={14} /> Detalhes</button>
                {canOperate && alert.status === "NOVO" && <button type="button" onClick={() => applyAction(alert.id, "analyze")}>Assumir</button>}
                {canOperate && !["DESCARTADO", "ENCERRADO"].includes(alert.status) && <button type="button" className="primaryButton" onClick={() => onAlertOccurrence(alert.id)}>Ocorrência</button>}
              </div>
            </div>
          ))}
        </div>
      </div>

      {selected && (
        <DetailModal title={`Alerta #${selected.id} — ${selected.event_type}`} onClose={() => setSelected(null)}>
          <div className="alertDetailGrid">
            <section className="alertEvidencePanel">
              <div className="cardHeader"><h3>Evidência</h3><span>Evento #{selected.id}</span></div>
              {evidenceUrl ? (
                <img src={evidenceUrl} alt={`Evidência do alerta ${selected.id}`} />
              ) : (
                <div className="alertEvidenceEmpty"><FileImage size={40} /><b>Sem evidência disponível</b><span>O evento pode ter sido criado sem captura de quadro.</span></div>
              )}
              <div className="alertEvidenceMeta">
                <span>Prioridade <b>{priorityLabel(selected.priority)}</b></span>
                <span>Registrado <b>{new Date(selected.event_occurred_at || selected.created_at).toLocaleString("pt-BR")}</b></span>
              </div>
            </section>

            <section className="alertLivePanel">
              <div className="cardHeader"><h3>Vídeo ao vivo</h3><span>SUB</span></div>
              {selected.camera_id ? (
                <div className="alertLiveFrame"><SecureStreamFrame cameraId={selected.camera_id} profile="SUB" title={`Alerta ${selected.id}`} /></div>
              ) : (
                <div className="alertEvidenceEmpty"><Camera size={40} /><b>Câmera não vinculada</b></div>
              )}
            </section>
          </div>

          <div className="alertDetailSummary">
            <article><span>Escola</span><b>{selected.school_name}</b></article>
            <article><span>Câmera</span><b>{selected.camera_name}</b></article>
            <article><span>Status</span><b>{selected.status.replaceAll("_", " ")}</b></article>
            <article><span>Responsável</span><b>{selected.assigned_user_name || "Não atribuído"}</b></article>
          </div>

          <section className="alertAssignmentBox">
            <div>
              <b>Atribuir responsável</b>
              <span>Informe o nome do operador ou equipe que assumirá a triagem.</span>
            </div>
            <input value={assignmentName} onChange={(event) => setAssignmentName(event.target.value)} placeholder="Nome do responsável" />
            <button type="button" onClick={assignAlert}>Salvar atribuição</button>
          </section>

          {canOperate && (
            <div className="alertWorkflowActions">
              <button type="button" onClick={() => applyAction(selected.id, "analyze")}>Em atendimento</button>
              <button type="button" onClick={() => applyAction(selected.id, "confirm")}>Confirmar</button>
              <button type="button" className="primaryButton" onClick={() => onAlertOccurrence(selected.id)}>Abrir ocorrência</button>
              <button type="button" className="dangerOutline" onClick={() => applyAction(selected.id, "dismiss")}>Descartar</button>
              <button type="button" onClick={() => applyAction(selected.id, "close")}>Encerrar</button>
            </div>
          )}

          <section className="alertTimelinePanel">
            <div className="cardHeader"><h3>Histórico do atendimento</h3><span>{selected.activities?.length || 0}</span></div>
            <div className="operationsTimeline">
              {(selected.activities || []).map((activity) => (
                <article key={activity.id}>
                  <span className="timelineDot" />
                  <div>
                    <b>{activity.action.replaceAll("_", " ")}</b>
                    <span>{activity.note || `${activity.from_status || "—"} → ${activity.to_status || "—"}`}</span>
                    <small>{new Date(activity.created_at).toLocaleString("pt-BR")} · {activity.user_name}</small>
                  </div>
                </article>
              ))}
            </div>
          </section>
        </DetailModal>
      )}
    </Page>
  );
}

function OccurrencesPage({ occurrences, form, setForm, onSubmit, onUpdate, teams, canOperate, onDetails }) {
  return (
    <Page title="Ocorrências" subtitle="Registro, acompanhamento e encerramento operacional">
      <div className={`twoColumn occurrenceLayout ${!canOperate ? "singleColumn" : ""}`}>
        {canOperate && <form className="formCard" onSubmit={onSubmit}>
          <h2>Abrir ocorrência</h2>
          <Field label="Escola">
            <input required value={form.school_name} onChange={(e) => setForm({ ...form, school_name: e.target.value })} />
          </Field>
          <Field label="Categoria">
            <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
              <option value="SEGURANCA">Segurança</option>
              <option value="TECNICA">Técnica</option>
              <option value="PATRIMONIAL">Patrimonial</option>
            </select>
          </Field>
          <Field label="Prioridade">
            <select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}>
              <option value="BAIXA">Baixa</option>
              <option value="MEDIA">Média</option>
              <option value="ALTA">Alta</option>
              <option value="CRITICA">Crítica</option>
            </select>
          </Field>
          <Field label="Descrição">
            <textarea required value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </Field>
          <Field label="Equipe responsável">
            <select value={form.assigned_team} onChange={(e) => setForm({ ...form, assigned_team: e.target.value })}>
              <option value="">Definir no despacho</option>
              {teams.map((team) => (
                <option key={team.id} value={team.name}>{team.name} — {team.status}</option>
              ))}
            </select>
          </Field>
          <button className="primaryButton"><Plus size={18} />Abrir ocorrência</button>
        </form>}

        <div className="dataCard">
          <div className="cardHeader"><h2>Ocorrências</h2><span>{occurrences.length}</span></div>
          <div className="records">
            {occurrences.length === 0 && <Empty text="Nenhuma ocorrência aberta." />}
            {occurrences.map((occurrence) => (
              <article className="occurrenceRecord" key={occurrence.id}>
                <div className="occurrenceTop">
                  <b>{occurrence.protocol}</b>
                  <span className={`statusPill ${occurrence.status === "ENCERRADA" ? "success" : "warning"}`}>{occurrence.status}</span>
                </div>
                <h3>{occurrence.school_name}</h3>
                <p>{occurrence.description}</p>
                <small>{occurrence.category} · {occurrence.priority} · {occurrence.assigned_team || "Equipe não definida"}</small>
                <button className="detailButton" onClick={() => onDetails(occurrence.id)}>Abrir detalhes</button>
                {canOperate && <div className="occurrenceActions">
                  <button onClick={() => onUpdate(occurrence.id, "EM_ANALISE")}>Em análise</button>
                  <button onClick={() => onUpdate(occurrence.id, "DESPACHADA", occurrence.assigned_team || "Equipe 01")}>Despachar</button>
                  <button onClick={() => onUpdate(occurrence.id, "EM_ATENDIMENTO")}>Em atendimento</button>
                  <button className="successButton" onClick={() => onUpdate(occurrence.id, "ENCERRADA")}>Encerrar</button>
                </div>}
              </article>
            ))}
          </div>
        </div>
      </div>
    </Page>
  );
}

function DispatchPage({
  occurrences,
  teams,
  teamForm,
  setTeamForm,
  onCreateTeam,
  onUpdate,
  onTeamStatus,
  canOperate,
}) {
  const active = occurrences.filter((item) => item.status !== "ENCERRADA");
  const availableTeams = teams.filter((team) => team.status === "DISPONIVEL");

  return (
    <Page title="Despacho" subtitle="Equipes, acionamentos e tempo operacional">
      <div className="dispatchSummary">
        <article><b>{availableTeams.length}</b><span>Equipes disponíveis</span></article>
        <article><b>{teams.filter((team) => team.status === "ACIONADA").length}</b><span>Equipes acionadas</span></article>
        <article><b>{teams.filter((team) => team.status === "EM_ATENDIMENTO").length}</b><span>Em atendimento</span></article>
        <article><b>{active.length}</b><span>Ocorrências ativas</span></article>
      </div>

      <div className="dispatchLayout">
        {canOperate && <form className="formCard teamForm" onSubmit={onCreateTeam}>
          <h2>Cadastrar equipe</h2>
          <Field label="Nome da equipe">
            <input required value={teamForm.name} onChange={(e) => setTeamForm({ ...teamForm, name: e.target.value })} />
          </Field>
          <Field label="Tipo">
            <select value={teamForm.team_type} onChange={(e) => setTeamForm({ ...teamForm, team_type: e.target.value })}>
              <option value="INTERNA">Equipe interna</option>
              <option value="DIRECAO">Direção escolar</option>
              <option value="GUARDA">Guarda</option>
              <option value="MANUTENCAO">Manutenção</option>
              <option value="SAUDE">Saúde</option>
            </select>
          </Field>
          <Field label="Telefone">
            <input value={teamForm.phone} onChange={(e) => setTeamForm({ ...teamForm, phone: e.target.value })} />
          </Field>
          <Field label="Observações">
            <textarea value={teamForm.notes} onChange={(e) => setTeamForm({ ...teamForm, notes: e.target.value })} />
          </Field>
          <button className="primaryButton"><Plus size={18} />Cadastrar equipe</button>

          <div className="teamList">
            <h3>Equipes operacionais</h3>
            {teams.map((team) => (
              <article className="teamCard" key={team.id}>
                <div>
                  <b>{team.name}</b>
                  <small>{team.team_type} · {team.phone || "Sem telefone"}</small>
                </div>
                <span className={`statusPill ${team.status === "DISPONIVEL" ? "success" : team.status === "INDISPONIVEL" ? "danger" : "warning"}`}>
                  {team.status}
                </span>
                <select value={team.status} onChange={(e) => onTeamStatus(team.id, e.target.value)}>
                  <option value="DISPONIVEL">Disponível</option>
                  <option value="ACIONADA">Acionada</option>
                  <option value="EM_DESLOCAMENTO">Em deslocamento</option>
                  <option value="EM_ATENDIMENTO">Em atendimento</option>
                  <option value="INDISPONIVEL">Indisponível</option>
                </select>
              </article>
            ))}
          </div>
        </form>}

        <div className="dispatchBoard">
          {["ABERTA", "DESPACHADA", "EM_ATENDIMENTO"].map((status) => (
            <section className="dispatchColumn" key={status}>
              <h2>{status.replaceAll("_", " ")}</h2>
              {active.filter((item) => item.status === status).map((item) => (
                <article className="dispatchCard" key={item.id}>
                  <b>{item.protocol}</b>
                  <h3>{item.school_name}</h3>
                  <p>{item.description}</p>
                  <small>{item.assigned_team || "Sem equipe"}</small>

                  {status === "ABERTA" && (
                    <div className="dispatchAssign">
                      <select
                        defaultValue=""
                        onChange={(event) => {
                          if (event.target.value) {
                            onUpdate(item.id, "DESPACHADA", event.target.value);
                          }
                        }}
                      >
                        <option value="">Selecionar equipe</option>
                        {availableTeams.map((team) => (
                          <option key={team.id} value={team.name}>{team.name}</option>
                        ))}
                      </select>
                    </div>
                  )}

                  {status === "DESPACHADA" && (
                    <button onClick={() => onUpdate(item.id, "EM_ATENDIMENTO")}>
                      Registrar chegada
                    </button>
                  )}

                  {status === "EM_ATENDIMENTO" && (
                    <button onClick={() => onUpdate(item.id, "ENCERRADA")}>
                      Encerrar atendimento
                    </button>
                  )}
                </article>
              ))}
            </section>
          ))}
        </div>
      </div>
    </Page>
  );
}

function EquipmentPage({
  equipment,
  schools,
  form,
  setForm,
  onSubmit,
  onDelete,
  onMaintenance,
  canWrite,
}) {
  const schoolName = (id) => schools.find((school) => school.id === id)?.name || "Sem escola";
  return (
    <Page title="Equipamentos" subtitle="Inventário, patrimônio, garantia e manutenção">
      <div className={`twoColumn wideForm ${!canWrite ? "singleColumn" : ""}`}>
        {canWrite && <form className="formCard" onSubmit={onSubmit}>
          <h2>Novo equipamento</h2>
          <div className="formGrid">
            <Field label="Escola">
              <select value={form.school_id} onChange={(e) => setForm({ ...form, school_id: e.target.value })}>
                <option value="">Sem vínculo</option>
                {schools.map((school) => <option key={school.id} value={school.id}>{school.name}</option>)}
              </select>
            </Field>
            <Field label="Categoria">
              <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                <option value="CAMERA">Câmera</option>
                <option value="NVR">NVR</option>
                <option value="SWITCH_POE">Switch PoE</option>
                <option value="TOTEM">Totem</option>
                <option value="NOBREAK">Nobreak</option>
                <option value="GATEWAY">Gateway</option>
                <option value="ROTEADOR">Roteador</option>
                <option value="SERVIDOR">Servidor</option>
                <option value="LINK">Link</option>
                <option value="OUTRO">Outro</option>
              </select>
            </Field>
            <Field label="Nome">
              <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </Field>
            <Field label="Fabricante">
              <input value={form.manufacturer} onChange={(e) => setForm({ ...form, manufacturer: e.target.value })} />
            </Field>
            <Field label="Modelo">
              <input value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })} />
            </Field>
            <Field label="Número de série">
              <input value={form.serial_number} onChange={(e) => setForm({ ...form, serial_number: e.target.value })} />
            </Field>
            <Field label="Patrimônio">
              <input value={form.asset_number} onChange={(e) => setForm({ ...form, asset_number: e.target.value })} />
            </Field>
            <Field label="Localização">
              <input value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} />
            </Field>
            <Field label="Status">
              <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
                <option value="OPERACIONAL">Operacional</option>
                <option value="MANUTENCAO">Manutenção</option>
                <option value="OFFLINE">Offline</option>
                <option value="ESTOQUE">Estoque</option>
                <option value="BAIXADO">Baixado</option>
              </select>
            </Field>
            <Field label="Data de instalação">
              <input type="date" value={form.installed_at} onChange={(e) => setForm({ ...form, installed_at: e.target.value })} />
            </Field>
            <Field label="Garantia até">
              <input type="date" value={form.warranty_until} onChange={(e) => setForm({ ...form, warranty_until: e.target.value })} />
            </Field>
          </div>
          <Field label="Observações">
            <textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
          </Field>
          <button className="primaryButton"><Plus size={18} />Cadastrar equipamento</button>
        </form>}

        <div className="dataCard">
          <div className="cardHeader"><h2>Inventário</h2><span>{equipment.length}</span></div>
          <div className="records">
            {equipment.length === 0 && <Empty text="Nenhum equipamento cadastrado." />}
            {equipment.map((item) => (
              <article className="record expandedRecord" key={item.id}>
                <span className="recordIcon"><Server /></span>
                <div>
                  <b>{item.name}</b>
                  <span>{item.category} · {schoolName(item.school_id)}</span>
                  <small>{item.manufacturer || "Sem fabricante"} {item.model || ""} · Série: {item.serial_number || "não informada"}</small>
                  <small>Patrimônio: {item.asset_number || "não informado"} · {item.location || "sem localização"}</small>
                </div>
                <div className="recordActions">
                  <span className={`statusPill ${item.status === "OPERACIONAL" ? "success" : item.status === "MANUTENCAO" ? "warning" : "danger"}`}>{item.status}</span>
                  {canWrite && <button type="button" onClick={() => onMaintenance(item.id)}>Manutenção</button>}
                  {canWrite && <button type="button" className="dangerOutline" onClick={() => onDelete(item.id)}><Trash2 size={14} />Excluir</button>}
                </div>
              </article>
            ))}
          </div>
        </div>
      </div>
    </Page>
  );
}

function ReportsPage({ data, occurrences, alerts, onExport }) {
  const cards = [
    ["Escolas", data.schools || 0],
    ["Câmeras", data.cameras || 0],
    ["Equipamentos", data.equipment || 0],
    ["Alertas ativos", data.alerts_active || 0],
    ["Ocorrências abertas", data.occurrences_open || 0],
    ["Manutenções abertas", data.maintenance_open || 0],
  ];
  return (
    <Page title="Relatórios" subtitle="Indicadores gerenciais e operacionais consolidados">
      <div className="reportActions">
        <button onClick={() => onExport("/reports/export/occurrences.csv", "eduvigia-ocorrencias.csv")}>
          Exportar ocorrências CSV
        </button>
        <button onClick={() => onExport("/reports/export/equipment.csv", "eduvigia-equipamentos.csv")}>
          Exportar equipamentos CSV
        </button>
      </div>
      <div className="reportCards">
        {cards.map(([label, value]) => (
          <article key={label}><span>{label}</span><b>{value}</b></article>
        ))}
      </div>
      <div className="reportGrid">
        <section className="dataCard">
          <div className="cardHeader"><h2>Disponibilidade de câmeras</h2></div>
          <div className="reportBars">
            <div><span>Online</span><b>{data.camera_online || 0}</b></div>
            <div><span>Offline</span><b>{data.camera_offline || 0}</b></div>
          </div>
        </section>
        <section className="dataCard">
          <div className="cardHeader"><h2>Ocorrências recentes</h2></div>
          <div className="records">
            {occurrences.slice(0, 6).map((item) => (
              <article className="miniRecord" key={item.id}>
                <b>{item.protocol}</b><span>{item.school_name}</span><small>{item.status} · {item.priority}</small>
              </article>
            ))}
          </div>
        </section>
        <section className="dataCard">
          <div className="cardHeader"><h2>Alertas recentes</h2></div>
          <div className="records">
            {alerts.slice(0, 6).map((item) => (
              <article className="miniRecord" key={item.id}>
                <b>{item.event_type}</b><span>{item.school_name}</span><small>{item.status} · {item.priority}</small>
              </article>
            ))}
          </div>
        </section>
      </div>
    </Page>
  );
}


function SecurityPage() {
  const [overview, setOverview] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);

  const loadSecurity = async () => {
    try {
      const [overviewData, sessionData] = await Promise.all([
        api("/security/overview"),
        api("/auth/sessions"),
      ]);
      setOverview(overviewData);
      setSessions(sessionData);
      setMessage("");
    } catch (error) {
      setMessage(error.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSecurity();
  }, []);

  const encryptExisting = async () => {
    try {
      const result = await api("/security/encrypt-existing-credentials", {
        method: "POST",
      });
      setMessage(
        `Credenciais protegidas: ${result.updated_recorders} gravador(es) e ${result.updated_cameras} câmera(s).`
      );
      await loadSecurity();
    } catch (error) {
      setMessage(error.message);
    }
  };

  const revokeSession = async (id) => {
    try {
      await api(`/auth/sessions/${id}`, { method: "DELETE" });
      setMessage("Sessão revogada.");
      await loadSecurity();
    } catch (error) {
      setMessage(error.message);
    }
  };

  return (
    <Page
      title="Segurança e LGPD"
      subtitle="Credenciais técnicas, sessões, bloqueios e controles de acesso"
    >
      {message && <div className="securityMessage">{message}</div>}
      {loading && <div className="monitorEmpty"><RefreshCw size={28} /><b>Carregando controles de segurança...</b></div>}

      {!loading && overview && (
        <>
          <div className="securityKpis">
            <article>
              <span>Sessões ativas</span>
              <b>{overview.active_sessions}</b>
            </article>
            <article>
              <span>Usuários bloqueados</span>
              <b>{overview.locked_users}</b>
            </article>
            <article>
              <span>Falhas de login em 24h</span>
              <b>{overview.recent_login_failures_24h}</b>
            </article>
            <article className={overview.credential_key_configured ? "secureCard" : "warningCard"}>
              <span>Chave de credenciais</span>
              <b>{overview.credential_key_configured ? "ATIVA" : "AUSENTE"}</b>
            </article>
          </div>

          <div className="securityGrid">
            <section className="dataCard">
              <div className="cardHeader">
                <h2>Proteção das credenciais</h2>
                <ShieldCheck size={20} />
              </div>
              <div className="securityDetails">
                <p>
                  Gravadores protegidos: <b>{overview.encrypted_recorder_credentials}</b> de{" "}
                  <b>{overview.recorder_credentials}</b>
                </p>
                <p>
                  Câmeras protegidas: <b>{overview.encrypted_camera_credentials}</b> de{" "}
                  <b>{overview.camera_credentials}</b>
                </p>
                <button
                  type="button"
                  className="primaryButton"
                  onClick={encryptExisting}
                  disabled={!overview.credential_key_configured}
                >
                  <ShieldCheck size={16} /> Proteger credenciais existentes
                </button>
                {!overview.credential_key_configured && (
                  <small>Configure EDUVIGIA_CREDENTIAL_KEY no arquivo .env.</small>
                )}
              </div>
            </section>

            <section className="dataCard">
              <div className="cardHeader"><h2>Políticas ativas</h2></div>
              <div className="securityPolicyList">
                <span>Senha mínima: <b>{overview.password_policy.minimum_length} caracteres</b></span>
                <span>Maiúscula, minúscula, número e caractere especial</span>
                <span>
                  Bloqueio após <b>{overview.lockout_policy.attempts}</b> tentativas por{" "}
                  <b>{overview.lockout_policy.minutes} minutos</b>
                </span>
                <span>Tokens de sessão armazenados em hash SHA-256</span>
                <span>CORS restrito às origens configuradas</span>
              </div>
            </section>
          </div>

          <section className="dataCard securitySessions">
            <div className="cardHeader">
              <h2>Minhas sessões</h2>
              <span>{sessions.length}</span>
            </div>
            <div className="records">
              {sessions.length === 0 && <Empty text="Nenhuma sessão ativa." />}
              {sessions.map((session) => (
                <article className="record expandedRecord" key={session.id}>
                  <span className="recordIcon"><CircleUserRound /></span>
                  <div>
                    <b>{session.ip_address || "IP não identificado"}</b>
                    <span>{session.user_agent || "Navegador não identificado"}</span>
                    <small>
                      Criada em {new Date(session.created_at).toLocaleString("pt-BR")} ·
                      Último uso {session.last_seen_at ? new Date(session.last_seen_at).toLocaleString("pt-BR") : "não registrado"}
                    </small>
                  </div>
                  <div className="recordActions">
                    <button type="button" className="dangerOutline" onClick={() => revokeSession(session.id)}>
                      Encerrar sessão
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </section>
        </>
      )}
    </Page>
  );
}


function SettingsPage({
  settings,
  onSave,
  authUser,
  users,
  schools,
  userForm,
  setUserForm,
  onCreateUser,
  onUpdateUser,
  onResetPassword,
  passwordForm,
  setPasswordForm,
  onChangePassword,
}) {
  const [values, setValues] = useState({});
  const [editingUserId, setEditingUserId] = useState(null);
  const [editUser, setEditUser] = useState({
    name: "",
    email: "",
    role: "OPERADOR_GUARDA",
    school_id: "",
    active: true,
  });
  const [userSearch, setUserSearch] = useState("");
  useEffect(() => {
    const next = {};
    settings.forEach((item) => { next[item.key] = item.value; });
    setValues(next);
  }, [settings]);

  const canManageUsers = authUser.role === "ADMIN_SECRETARIA";
  const filteredUsers = users.filter((user) => {
    const text = `${user.name} ${user.email} ${user.role} ${user.school_name || ""}`.toLowerCase();
    return text.includes(userSearch.toLowerCase());
  });

  const startEditUser = (user) => {
    setEditingUserId(user.id);
    setEditUser({
      name: user.name,
      email: user.email,
      role: user.role,
      school_id: user.school_id ? String(user.school_id) : "",
      active: user.active,
    });
  };

  const saveEditedUser = async (event) => {
    event.preventDefault();
    const ok = await onUpdateUser(editingUserId, editUser);
    if (ok) setEditingUserId(null);
  };

  return (
    <Page title="Configurações" subtitle="Usuários, segurança e parâmetros operacionais">
      {authUser.must_change_password && (
        <div className="securityWarning">
          A senha utilizada é temporária. Altere-a antes de continuar utilizando o sistema.
        </div>
      )}

      <div className="settingsSection">
        <h2>Minha segurança</h2>
        <form className="passwordCard" onSubmit={onChangePassword}>
          <Field label="Senha atual">
            <input
              type="password"
              required
              value={passwordForm.current_password}
              onChange={(e) => setPasswordForm({ ...passwordForm, current_password: e.target.value })}
            />
          </Field>
          <Field label="Nova senha">
            <input
              type="password"
              required
              minLength={10}
              value={passwordForm.new_password}
              onChange={(e) => setPasswordForm({ ...passwordForm, new_password: e.target.value })}
            />
          </Field>
          <button className="primaryButton">Alterar minha senha</button>
        </form>
      </div>

      {canManageUsers && (
        <div className="settingsSection">
          <h2>Usuários e perfis</h2>
          <div className="userManagement">
            <form className="formCard" onSubmit={onCreateUser}>
              <Field label="Nome">
                <input required value={userForm.name} onChange={(e) => setUserForm({ ...userForm, name: e.target.value })} />
              </Field>
              <Field label="E-mail">
                <input type="email" required value={userForm.email} onChange={(e) => setUserForm({ ...userForm, email: e.target.value })} />
              </Field>
              <Field label="Senha temporária">
                <input type="password" required minLength={10} value={userForm.password} onChange={(e) => setUserForm({ ...userForm, password: e.target.value })} />
              </Field>
              <Field label="Perfil">
                <select value={userForm.role} onChange={(e) => setUserForm({ ...userForm, role: e.target.value })}>
                  {ROLE_OPTIONS.map(([value, label, environment]) => (
                    <option key={value} value={value}>{label} · {environment}</option>
                  ))}
                </select>
              </Field>
              <Field label="Escola vinculada">
                <select
                  required={SCHOOL_ROLES.has(userForm.role)}
                  value={userForm.school_id}
                  onChange={(e) => setUserForm({ ...userForm, school_id: e.target.value })}
                >
                  <option value="">
                    {SCHOOL_ROLES.has(userForm.role) ? "Selecione uma escola" : userForm.role === "TECNICO" ? "Sem vínculo (todas as escolas)" : "Sem vínculo específico"}
                  </option>
                  {schools.map((school) => <option key={school.id} value={school.id}>{school.name}</option>)}
                </select>
              </Field>
              <button className="primaryButton"><Plus size={18} />Cadastrar usuário</button>
            </form>

            <div className="dataCard userDirectory">
              <div className="cardHeader">
                <div>
                  <h2>Usuários cadastrados</h2>
                  <small>Contas individuais, perfis e vínculo escolar</small>
                </div>
                <span>{users.length}</span>
              </div>

              <div className="userSearchBox">
                <Search size={17} />
                <input
                  value={userSearch}
                  onChange={(event) => setUserSearch(event.target.value)}
                  placeholder="Buscar por nome, e-mail, perfil ou escola"
                />
              </div>

              <div className="records">
                {filteredUsers.map((user) => (
                  <article className="record expandedRecord userRecord" key={user.id}>
                    {editingUserId === user.id ? (
                      <form className="userEditForm" onSubmit={saveEditedUser}>
                        <Field label="Nome">
                          <input
                            required
                            value={editUser.name}
                            onChange={(e) => setEditUser({ ...editUser, name: e.target.value })}
                          />
                        </Field>
                        <Field label="E-mail">
                          <input
                            required
                            type="email"
                            value={editUser.email}
                            onChange={(e) => setEditUser({ ...editUser, email: e.target.value })}
                          />
                        </Field>
                        <Field label="Perfil">
                          <select
                            value={editUser.role}
                            onChange={(e) => setEditUser({ ...editUser, role: e.target.value })}
                          >
                            {ROLE_OPTIONS.map(([value, label, environment]) => (
                              <option key={value} value={value}>{label} · {environment}</option>
                            ))}
                          </select>
                        </Field>
                        <Field label="Escola vinculada">
                          <select
                            required={SCHOOL_ROLES.has(editUser.role)}
                            value={editUser.school_id}
                            onChange={(e) => setEditUser({ ...editUser, school_id: e.target.value })}
                          >
                            <option value="">
                              {SCHOOL_ROLES.has(editUser.role) ? "Selecione uma escola" : editUser.role === "TECNICO" ? "Sem vínculo (todas as escolas)" : "Sem vínculo específico"}
                            </option>
                            {schools.map((school) => (
                              <option key={school.id} value={school.id}>{school.name}</option>
                            ))}
                          </select>
                        </Field>
                        <label className="userActiveToggle">
                          <input
                            type="checkbox"
                            checked={editUser.active}
                            onChange={(e) => setEditUser({ ...editUser, active: e.target.checked })}
                          />
                          Usuário ativo
                        </label>
                        <div className="userEditActions">
                          <button type="button" onClick={() => setEditingUserId(null)}>Cancelar</button>
                          <button type="submit" className="primaryButton">Salvar alterações</button>
                        </div>
                      </form>
                    ) : (
                      <>
                        <span className="recordIcon"><CircleUserRound /></span>
                        <div>
                          <b>{user.name}</b>
                          <span>{user.email}</span>
                          <small>
                            {roleLabel(user.role)}
                            {" · "}
                            {user.school_name || "Acesso global"}
                            {" · "}
                            {user.must_change_password ? "Senha temporária" : "Senha definida"}
                          </small>
                        </div>
                        <div className="recordActions">
                          <span className={`statusPill ${user.active ? "success" : "danger"}`}>
                            {user.active ? "ATIVO" : "INATIVO"}
                          </span>
                          <button type="button" onClick={() => startEditUser(user)}>Editar</button>
                          <button type="button" onClick={() => onResetPassword(user.id)}>
                            Redefinir senha
                          </button>
                        </div>
                      </>
                    )}
                  </article>
                ))}
                {filteredUsers.length === 0 && <Empty text="Nenhum usuário encontrado." />}
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="settingsSection">
        <h2>Parâmetros operacionais</h2>
        <div className="settingsGrid">
          {settings.map((item) => (
            <article className="settingCard" key={item.key}>
              <div>
                <b>{item.key}</b>
                <span>{item.description || "Parâmetro do sistema"}</span>
              </div>
              <input value={values[item.key] ?? item.value} onChange={(e) => setValues({ ...values, [item.key]: e.target.value })} />
              <button onClick={() => onSave(item.key, values[item.key] ?? item.value, item.description)}>Salvar</button>
            </article>
          ))}
        </div>
      </div>
    </Page>
  );
}


function PasswordChangeGate({ user, form, setForm, onSubmit, onLogout, onSupport, message }) {
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);

  return (
    <div className="passwordGatePage">
      <div className="passwordGateCard">
        <img src="/eduvigia-brand.png" alt="EduVigIA" />
        <div className="passwordGateIcon"><ShieldCheck size={34} /></div>
        <h1>Proteja sua conta antes de continuar</h1>
        <p>
          Olá, <b>{user.name}</b>. Esta conta está usando uma senha temporária.
          A troca é obrigatória para liberar o ambiente EduVigIA.
        </p>

        {message && (
          <div className="loginError schoolLoginError" role="alert">
            <AlertTriangle size={18} />
            <span>{message}</span>
          </div>
        )}

        <form onSubmit={onSubmit}>
          <Field label="Senha atual">
            <div className="schoolLoginInput">
              <ShieldCheck size={19} />
              <input
                type={showCurrent ? "text" : "password"}
                required
                autoComplete="current-password"
                value={form.current_password}
                onChange={(event) => setForm({ ...form, current_password: event.target.value })}
              />
              <button
                className="schoolPasswordToggle"
                type="button"
                onClick={() => setShowCurrent((current) => !current)}
                aria-label={showCurrent ? "Ocultar senha atual" : "Mostrar senha atual"}
              >
                <Eye size={19} />
              </button>
            </div>
          </Field>

          <Field label="Nova senha segura">
            <div className="schoolLoginInput">
              <ShieldCheck size={19} />
              <input
                type={showNew ? "text" : "password"}
                required
                minLength={10}
                autoComplete="new-password"
                value={form.new_password}
                onChange={(event) => setForm({ ...form, new_password: event.target.value })}
              />
              <button
                className="schoolPasswordToggle"
                type="button"
                onClick={() => setShowNew((current) => !current)}
                aria-label={showNew ? "Ocultar nova senha" : "Mostrar nova senha"}
              >
                <Eye size={19} />
              </button>
            </div>
          </Field>

          <div className="passwordPolicy">
            Mínimo de 10 caracteres, incluindo letra maiúscula, letra minúscula,
            número e caractere especial.
          </div>

          <button className="schoolLoginSubmit" type="submit">
            <ShieldCheck size={19} />
            Alterar senha e liberar ambiente
          </button>
        </form>

        <div className="passwordGateActions">
          <button type="button" onClick={onSupport}><Headphones size={16} />Suporte</button>
          <button type="button" onClick={onLogout}>Sair da conta</button>
        </div>
      </div>
    </div>
  );
}


function LoginPage({ form, setForm, onSubmit, message, loading, onSupport, onForgotPassword }) {
  const [showPassword, setShowPassword] = useState(false);

  return (
    <div className="schoolLoginPage">
      <section className="schoolLoginHero" aria-hidden="true">
        <div className="schoolLoginHeroImage" />
      </section>

      <section className="schoolLoginAccess">
        <button type="button" className="schoolLoginHelp" onClick={onSupport}>
          <Headphones size={16} />
          <span>Precisa de ajuda?</span>
          <b>Fale com o suporte</b>
        </button>

        <form className="schoolLoginCard" onSubmit={onSubmit}>
          <div className="schoolLoginLogo">
            <img src="/eduvigia-brand.png" alt="EduVigIA" />
            <span>Plataforma Integrada de Segurança Escolar</span>
          </div>

          <div className="schoolLoginWelcome">
            <span className="schoolCapIcon">🎓</span>
            <div>
              <h1>Bem-vindo de volta!</h1>
              <p>Acesse sua conta para continuar protegendo nossa comunidade escolar.</p>
            </div>
          </div>

          {message && (
            <div className="loginError schoolLoginError" role="alert">
              <AlertTriangle size={18} />
              <span>{message}</span>
            </div>
          )}

          <Field label="E-mail institucional">
            <div className="schoolLoginInput">
              <CircleUserRound size={19} />
              <input
                type="email"
                required
                autoComplete="username"
                value={form.email}
                onChange={(event) => setForm({ ...form, email: event.target.value })}
                placeholder="seu.nome@escola.edu.br"
              />
            </div>
          </Field>

          <Field label="Senha">
            <div className="schoolLoginInput">
              <ShieldCheck size={19} />
              <input
                type={showPassword ? "text" : "password"}
                required
                autoComplete="current-password"
                value={form.password}
                onChange={(event) => setForm({ ...form, password: event.target.value })}
                placeholder="Digite sua senha"
              />
              <button
                className="schoolPasswordToggle"
                type="button"
                onClick={() => setShowPassword((current) => !current)}
                aria-label={showPassword ? "Ocultar senha" : "Mostrar senha"}
              >
                <Eye size={19} />
              </button>
            </div>
          </Field>

          <div className="schoolForgotPassword">
            <span />
            <button type="button" onClick={onForgotPassword}>
              Esqueceu sua senha?
            </button>
          </div>

          <button className="schoolLoginSubmit" disabled={loading}>
            {loading ? (
              <>
                <RefreshCw size={19} className="spinIcon" />
                Validando acesso...
              </>
            ) : (
              <>
                <ShieldCheck size={19} />
                Entrar no sistema
              </>
            )}
          </button>

          <div className="schoolLoginDivider"><span>ou</span></div>

          <button className="schoolGoogleButton" type="button" disabled title="Integração futura">
            <b>G</b>
            Entrar com Google
          </button>

          <div className="schoolSecurityFooter">
            <ShieldCheck size={26} />
            <div>
              <b>Plataforma segura e auditada</b>
              <span>Seus dados e acessos são protegidos e registrados.</span>
            </div>
          </div>

          <div className="schoolFirstAccess">
            <span>Primeiro acesso administrativo</span>
            <code>admin@eduvigia.local</code>
          </div>
          <small className="loginVersion">EduVigIA v2.0.0-F7-R3</small>
        </form>
      </section>

      <footer className="schoolLoginFooter">
        <Building2 size={24} />
        <span>Educação segura. Alunos protegidos. Futuro garantido.</span>
        <small>© 2026 EduVigIA. Todos os direitos reservados.</small>
      </footer>
    </div>
  );
}

function Page({ title, subtitle, children }) {
  const cameraFleetStatus = useCameraFleetStatus();
  return (
    <>
      <div className="pageHeading">
        <div><h1>{title}</h1><p>{subtitle}</p></div>
        <span
          className={`statusPill ${cameraFleetStatus.tone}`}
          title={cameraFleetStatus.detail}
          aria-label={cameraFleetStatus.detail}
        >
          {cameraFleetStatus.label}
        </span>
      </div>
      {children}
    </>
  );
}

function Field({ label, children }) {
  return <label className="field"><span>{label}</span>{children}</label>;
}

function Empty({ text }) {
  return <div className="emptyState"><ShieldCheck size={38} /><span>{text}</span></div>;
}

function AuditPage({ logs }) {
  return (
    <Page title="Auditoria" subtitle="Rastreabilidade das decisões e alterações do sistema">
      <div className="dataCard full">
        <div className="cardHeader"><h2>Eventos registrados</h2><span>{logs.length}</span></div>
        <div className="auditTable">
          <div className="auditHead">
            <span>Data e hora</span>
            <span>Usuário</span>
            <span>Módulo</span>
            <span>Ação</span>
            <span>Detalhes</span>
          </div>
          {logs.map((log) => (
            <div className="auditRow" key={log.id}>
              <span>{new Date(log.created_at).toLocaleString("pt-BR")}</span>
              <span>{log.user_name}</span>
              <b>{log.module}</b>
              <span>{log.action}</span>
              <small>{log.details || "—"}</small>
            </div>
          ))}
          {logs.length === 0 && <Empty text="Nenhum evento de auditoria registrado." />}
        </div>
      </div>
    </Page>
  );
}


function InfrastructurePage({ onFeedback }) {
  const [data, setData] = useState(null);
  const [capacity, setCapacity] = useState(null);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);

  const loadInfrastructure = async ({ userInitiated = false } = {}) => {
    setLoading(true);
    try {
      const [overview, capacityData] = await Promise.all([
        api("/infrastructure/overview"),
        api("/infrastructure/capacity"),
      ]);
      setData(overview);
      setCapacity(capacityData);
      setMessage("");
      if (userInitiated) onFeedback?.("success", "Diagnóstico de infraestrutura atualizado", `Estado geral: ${overview.overall || "verificado"}.`);
      return true;
    } catch (error) {
      setMessage(error.message);
      if (userInitiated) onFeedback?.("error", "Falha no diagnóstico de infraestrutura", error.message || "Não foi possível atualizar o diagnóstico.");
      return false;
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadInfrastructure();
  }, []);

  const serviceClass = (status) => {
    if (status === "ONLINE") return "success";
    if (status === "OFFLINE") return "danger";
    return "warning";
  };

  return (
    <Page
      title="Infraestrutura"
      subtitle="Prontidão, banco, métricas, proxy HTTPS, capacidade e continuidade"
    >
      <div className="infraToolbar">
        <div>
          <b>{data?.overall || "VERIFICANDO"}</b>
          <span>
            {data?.checked_at
              ? `Última verificação: ${new Date(data.checked_at).toLocaleString("pt-BR")}`
              : "Aguardando diagnóstico"}
          </span>
        </div>
        <button type="button" onClick={() => loadInfrastructure({ userInitiated: true })} disabled={loading}>
          <RefreshCw size={16} className={loading ? "spinIcon" : ""} />
          {loading ? "Atualizando..." : "Atualizar diagnóstico"}
        </button>
      </div>

      {message && <div className="operationsError">{message}</div>}

      {loading && !data && (
        <div className="monitorEmpty">
          <RefreshCw size={30} className="spinIcon" />
          <b>Verificando infraestrutura...</b>
        </div>
      )}

      {data && (
        <>
          <div className="infraKpis">
            <article>
              <span>Ambiente</span>
              <b>{data.environment}</b>
              <small>EduVigIA {data.version}</small>
            </article>
            <article>
              <span>Armazenamento usado</span>
              <b>{data.storage.used_percent}%</b>
              <small>{data.storage.free_gb} GB livres</small>
            </article>
            <article>
              <span>Câmeras online</span>
              <b>{data.video.cameras_online}</b>
              <small>de {data.video.cameras_total}</small>
            </article>
            <article>
              <span>Gravadores online</span>
              <b>{data.video.recorders_online}</b>
              <small>de {data.video.recorders_total}</small>
            </article>
            <article>
              <span>Prontidão</span>
              <b>{data.readiness?.status || "N/D"}</b>
              <small>{data.readiness?.ready ? "Todos os serviços essenciais" : "Requer atenção"}</small>
            </article>
            <article>
              <span>Pool PostgreSQL</span>
              <b>{data.database_pool?.checked_out ?? 0}</b>
              <small>conexões em uso</small>
            </article>
          </div>

          <div className="infraGrid">
            <section className="dataCard">
              <div className="cardHeader">
                <h2>Serviços essenciais</h2>
                <span>{Object.keys(data.services).length}</span>
              </div>
              <div className="infraServiceList">
                {Object.entries(data.services).map(([name, service]) => (
                  <article key={name}>
                    <div>
                      <b>{name.replaceAll("_", " ")}</b>
                      <span>
                        {service.host && service.port
                          ? `${service.host}:${service.port}`
                          : "Serviço interno"}
                      </span>
                    </div>
                    <span className={`statusPill ${serviceClass(service.status)}`}>
                      {service.status}
                    </span>
                  </article>
                ))}
              </div>
            </section>

            <section className="dataCard">
              <div className="cardHeader"><h2>Armazenamento</h2></div>
              <div className="storageMeter">
                <div>
                  <span style={{ width: `${Math.min(data.storage.used_percent, 100)}%` }} />
                </div>
                <b>{data.storage.used_gb} GB de {data.storage.total_gb} GB</b>
                <small>{data.storage.path}</small>
              </div>
            </section>

            <section className="dataCard">
              <div className="cardHeader"><h2>Portas operacionais</h2></div>
              <div className="infraPorts">
                {Object.entries(data.ports).map(([name, port]) => (
                  <article key={name}>
                    <span>{name.replaceAll("_", " ")}</span>
                    <b>{port}</b>
                  </article>
                ))}
              </div>
            </section>

            <section className="dataCard">
              <div className="cardHeader"><h2>Política de backup</h2></div>
              <div className="infraBackup">
                <ShieldCheck size={34} />
                <div>
                  <b>Backup diário com restauração isolada</b>
                  <span>PostgreSQL custom format, evidências, configurações e hashes</span>
                  <small>Retenção: {data.backup?.retention_days || 30} dias.</small>
                </div>
              </div>
            </section>

            <section className="dataCard">
              <div className="cardHeader"><h2>Observabilidade</h2></div>
              <div className="infraServiceList">
                <article><div><b>Métricas Prometheus</b><span>/metrics</span></div><span className="statusPill success">ATIVO</span></article>
                <article><div><b>Logs estruturados</b><span>Request ID em cada resposta</span></div><span className="statusPill success">ATIVO</span></article>
                <article><div><b>Prometheus local</b><span>http://localhost:19090</span></div><span className="statusPill success">ATIVO</span></article>
              </div>
            </section>

            <section className="dataCard">
              <div className="cardHeader"><h2>Proxy e HTTPS</h2></div>
              <div className="infraBackup">
                <ShieldCheck size={34} />
                <div>
                  <b>Reverse proxy Nginx</b>
                  <span>HTTP 8088 e HTTPS 18443 com certificado local</span>
                  <small>O navegador pode alertar sobre certificado autoassinado.</small>
                </div>
              </div>
            </section>

            {capacity && (
              <section className="dataCard full">
                <div className="cardHeader"><h2>Capacidade e escalabilidade</h2><span>{capacity.scaling.state}</span></div>
                <div className="infraCapacityGrid">
                  <article><span>Escolas</span><b>{capacity.inventory.schools}</b></article>
                  <article><span>Câmeras</span><b>{capacity.inventory.cameras}</b></article>
                  <article><span>Sessões ativas</span><b>{capacity.inventory.active_sessions}</b></article>
                  <article><span>Workers sugeridos</span><b>{capacity.scaling.recommended_api_workers}</b></article>
                  <article><span>Pool configurado</span><b>{capacity.database_pool.configured_size || "N/D"}</b></article>
                  <article><span>Retenção de auditoria</span><b>{capacity.retention.audit_days} dias</b></article>
                </div>
                <small className="infraCapacityNote">{capacity.scaling.note}</small>
              </section>
            )}
          </div>
        </>
      )}
    </Page>
  );
}




function webMercatorPoint(latitude, longitude, zoom) {
  const lat = Math.max(-85.05112878, Math.min(85.05112878, Number(latitude)));
  const lon = Number(longitude);
  const scale = 2 ** zoom;
  const x = ((lon + 180) / 360) * scale;
  const radians = (lat * Math.PI) / 180;
  const y = (1 - Math.asinh(Math.tan(radians)) / Math.PI) / 2 * scale;
  return { x, y };
}

function fitOperationalMap(points, width = 900, height = 520) {
  if (!points.length) return { latitude: -14.235, longitude: -51.9253, zoom: 4 };
  const latitude = points.reduce((sum, item) => sum + Number(item.latitude), 0) / points.length;
  const longitude = points.reduce((sum, item) => sum + Number(item.longitude), 0) / points.length;
  if (points.length === 1) return { latitude, longitude, zoom: 16 };
  for (let zoom = 18; zoom >= 4; zoom -= 1) {
    const projected = points.map((item) => webMercatorPoint(item.latitude, item.longitude, zoom));
    const xs = projected.map((item) => item.x * 256);
    const ys = projected.map((item) => item.y * 256);
    if ((Math.max(...xs) - Math.min(...xs)) <= width * 0.66 && (Math.max(...ys) - Math.min(...ys)) <= height * 0.66) {
      return { latitude, longitude, zoom };
    }
  }
  return { latitude, longitude, zoom: 4 };
}

function OperationalMapCanvas({ points = [], selectedId = null, onSelect = () => {}, tileTemplate, attribution, fitKey = 0 }) {
  const containerRef = useRef(null);
  const [size, setSize] = useState({ width: 900, height: 520 });
  const [view, setView] = useState(() => fitOperationalMap(points));

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return undefined;
    const update = () => setSize({ width: Math.max(320, element.clientWidth), height: Math.max(360, element.clientHeight) });
    update();
    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(update) : null;
    observer?.observe(element);
    window.addEventListener("resize", update);
    return () => { observer?.disconnect(); window.removeEventListener("resize", update); };
  }, []);

  useEffect(() => {
    setView(fitOperationalMap(points, size.width, size.height));
  }, [fitKey, points.length]);

  const zoom = Math.max(3, Math.min(18, view.zoom));
  const centerWorld = webMercatorPoint(view.latitude, view.longitude, zoom);
  const centerPx = { x: centerWorld.x * 256, y: centerWorld.y * 256 };
  const leftWorld = centerPx.x - size.width / 2;
  const topWorld = centerPx.y - size.height / 2;
  const minTileX = Math.floor(leftWorld / 256) - 1;
  const maxTileX = Math.floor((leftWorld + size.width) / 256) + 1;
  const minTileY = Math.max(0, Math.floor(topWorld / 256) - 1);
  const maxTileY = Math.min((2 ** zoom) - 1, Math.floor((topWorld + size.height) / 256) + 1);
  const tiles = [];
  for (let y = minTileY; y <= maxTileY; y += 1) {
    for (let x = minTileX; x <= maxTileX; x += 1) {
      const modulus = 2 ** zoom;
      const wrappedX = ((x % modulus) + modulus) % modulus;
      const url = String(tileTemplate || "https://tile.openstreetmap.org/{z}/{x}/{y}.png")
        .replaceAll("{z}", String(zoom)).replaceAll("{x}", String(wrappedX)).replaceAll("{y}", String(y));
      tiles.push({ key: `${zoom}-${x}-${y}`, url, left: x * 256 - leftWorld, top: y * 256 - topWorld });
    }
  }

  return (
    <div className="operationalMapCanvas" ref={containerRef}>
      <div className="mapFallbackGrid" />
      {tiles.map((tile) => (
        <img key={tile.key} className="mapTile" src={tile.url} alt="" draggable="false" loading="lazy" style={{ left: tile.left, top: tile.top }} />
      ))}
      {points.map((point) => {
        const projected = webMercatorPoint(point.latitude, point.longitude, zoom);
        const left = projected.x * 256 - leftWorld;
        const top = projected.y * 256 - topWorld;
        if (left < -40 || top < -40 || left > size.width + 40 || top > size.height + 40) return null;
        return (
          <button
            key={point.school_id}
            type="button"
            className={`schoolMapMarker ${String(point.map_status || "NORMAL").toLowerCase()} ${Number(selectedId) === Number(point.school_id) ? "selected" : ""}`}
            style={{ left, top }}
            onClick={() => onSelect(point)}
            title={`${point.school_name} · ${point.cameras_online}/${point.cameras_total} câmeras online`}
          >
            <Building2 size={18} />
            <span>{point.school_name}</span>
            {(point.active_alerts > 0 || point.open_occurrences > 0) && <b>{point.active_alerts + point.open_occurrences}</b>}
          </button>
        );
      })}
      <div className="mapControls">
        <button type="button" onClick={() => setView((current) => ({ ...current, zoom: Math.min(18, current.zoom + 1) }))}>+</button>
        <button type="button" onClick={() => setView((current) => ({ ...current, zoom: Math.max(3, current.zoom - 1) }))}>−</button>
        <button type="button" title="Enquadrar todas" onClick={() => setView(fitOperationalMap(points, size.width, size.height))}><Crosshair size={16} /></button>
      </div>
      <div className="mapAttribution">{attribution || "© OpenStreetMap contributors"}</div>
    </div>
  );
}

function OperationalMapPage({ onNavigate = () => {}, onFeedback }) {
  const [data, setData] = useState({ points: [], unlocated: [], summary: {} });
  const [selected, setSelected] = useState(null);
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [fitKey, setFitKey] = useState(0);

  const loadMap = async ({ userInitiated = false } = {}) => {
    setLoading(true);
    try {
      const result = await api("/maps/overview");
      setData(result);
      setError("");
      setSelected((current) => result.points.find((item) => Number(item.school_id) === Number(current?.school_id)) || result.points[0] || null);
      setFitKey((value) => value + 1);
      if (userInitiated) onFeedback?.("success", "Mapa operacional atualizado", `${result.points?.length || 0} escola(s) georreferenciada(s) carregada(s).`);
      return true;
    } catch (loadError) {
      const detail = loadError.message || "Não foi possível carregar o mapa operacional.";
      setError(detail);
      if (userInitiated) onFeedback?.("error", "Falha ao atualizar mapa", detail);
      return false;
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadMap(); }, []);

  const filteredPoints = useMemo(() => data.points.filter((item) => {
    const statusMatch = statusFilter === "ALL" || item.map_status === statusFilter;
    const term = search.trim().toLowerCase();
    const searchMatch = !term || `${item.school_name} ${item.code || ""} ${item.address || ""} ${item.city || ""}`.toLowerCase().includes(term);
    return statusMatch && searchMatch;
  }), [data.points, statusFilter, search]);

  const summary = data.summary || {};
  const statusLabel = (status) => status === "CRITICAL" ? "CRÍTICA" : status === "ATTENTION" ? "ATENÇÃO" : "NORMAL";

  return (
    <Page title="Mapa Operacional" subtitle="Visão geográfica multi-escola com saúde de vídeo, alertas e ocorrências">
      <div className="mapOperationalToolbar">
        <div className="mapSearch"><Search size={17} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar escola, endereço ou cidade" /></div>
        <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
          <option value="ALL">Todas as situações</option>
          <option value="CRITICAL">Críticas</option>
          <option value="ATTENTION">Atenção</option>
          <option value="NORMAL">Normais</option>
        </select>
        <button type="button" onClick={() => loadMap({ userInitiated: true })} disabled={loading}><RefreshCw size={16} className={loading ? "spinIcon" : ""} /> {loading ? "Atualizando..." : "Atualizar mapa"}</button>
      </div>

      {error && <div className="operationsError">{error}</div>}

      <div className="mapKpis">
        <article><span>Escolas ativas</span><b>{summary.schools_total || 0}</b></article>
        <article><span>Georreferenciadas</span><b>{summary.schools_located || 0}</b></article>
        <article><span>Críticas</span><b>{summary.critical || 0}</b></article>
        <article><span>Atenção</span><b>{summary.attention || 0}</b></article>
        <article><span>Sem coordenadas</span><b>{summary.schools_unlocated || 0}</b></article>
      </div>

      <div className="operationalMapLayout">
        <section className="mapStageCard">
          <OperationalMapCanvas
            points={filteredPoints}
            selectedId={selected?.school_id}
            onSelect={setSelected}
            tileTemplate={data.tile_url_template}
            attribution={data.attribution}
            fitKey={fitKey}
          />
          <div className="mapLegend">
            <span><i className="normal" /> Normal</span>
            <span><i className="attention" /> Atenção</span>
            <span><i className="critical" /> Crítica</span>
            <small>Tiles configuráveis: no ambiente on-premises, a URL pode apontar para servidor cartográfico interno.</small>
          </div>
        </section>

        <aside className="mapSidePanel">
          {selected ? (
            <>
              <div className="mapSelectedHeader">
                <span className={`mapStatusDot ${String(selected.map_status).toLowerCase()}`} />
                <div><h3>{selected.school_name}</h3><span>{selected.code || "Sem código"} · {selected.city || "Cidade não informada"}</span></div>
              </div>
              <p>{selected.address}</p>
              <div className="mapSelectedStats">
                <div><b>{selected.cameras_online}/{selected.cameras_total}</b><span>Câmeras online</span></div>
                <div><b>{selected.cameras_offline}</b><span>Offline</span></div>
                <div><b>{selected.active_alerts}</b><span>Alertas</span></div>
                <div><b>{selected.open_occurrences}</b><span>Ocorrências</span></div>
              </div>
              <span className={`statusPill ${selected.map_status === "CRITICAL" ? "danger" : selected.map_status === "ATTENTION" ? "warning" : "success"}`}>{statusLabel(selected.map_status)}</span>
              <div className="mapSideActions">
                <button type="button" className="primaryButton" onClick={() => onNavigate("monitor")}><Video size={16} /> Abrir monitoramento</button>
                <button type="button" onClick={() => onNavigate("floorplans")}><FileImage size={16} /> Abrir plantas baixas</button>
                <button type="button" onClick={() => onNavigate("schools")}><Building2 size={16} /> Cadastro da escola</button>
              </div>
            </>
          ) : (
            <div className="monitorEmpty"><MapPinned size={30} /><b>Selecione uma escola no mapa</b><span>O painel mostrará câmeras, alertas e ocorrências.</span></div>
          )}

          {data.unlocated?.length > 0 && (
            <div className="mapUnlocated">
              <h4>Sem coordenadas ({data.unlocated.length})</h4>
              {data.unlocated.slice(0, 12).map((item) => <button type="button" key={item.school_id} onClick={() => onNavigate("schools")}><b>{item.school_name}</b><span>Cadastre latitude e longitude</span></button>)}
            </div>
          )}
        </aside>
      </div>
    </Page>
  );
}

function FloorPlansPage({ schools = [], cameras = [], canWrite = false, onNavigate = () => {} }) {
  const [schoolId, setSchoolId] = useState("");
  const [plans, setPlans] = useState([]);
  const [activeId, setActiveId] = useState("");
  const [imageUrl, setImageUrl] = useState("");
  const [selectedCameraId, setSelectedCameraId] = useState("");
  const [placements, setPlacements] = useState([]);
  const [message, setMessage] = useState("");
  const [uploading, setUploading] = useState(false);
  const [form, setForm] = useState({ name: "", building: "", floor_label: "", file: null });

  useEffect(() => {
    if (!schoolId && schools.length) setSchoolId(String(schools[0].id));
  }, [schools, schoolId]);

  const schoolCameras = useMemo(
    () => cameras.filter((camera) => Number(camera.school_id) === Number(schoolId)),
    [cameras, schoolId]
  );
  const activePlan = plans.find((item) => String(item.id) === String(activeId)) || null;

  const loadPlans = async (preferredId = null) => {
    if (!schoolId) { setPlans([]); setActiveId(""); return; }
    try {
      const rows = await api(`/floor-plans?school_id=${schoolId}`);
      setPlans(rows || []);
      const preferred = preferredId ? rows.find((row) => Number(row.id) === Number(preferredId)) : rows[0];
      setActiveId(preferred ? String(preferred.id) : "");
      setPlacements(preferred?.placements || []);
      setMessage("");
    } catch (error) { setMessage(error.message); }
  };

  useEffect(() => { loadPlans(); }, [schoolId]);

  useEffect(() => {
    const plan = plans.find((item) => String(item.id) === String(activeId));
    setPlacements(plan?.placements || []);
    setSelectedCameraId("");
    let revoked = false;
    let localUrl = "";
    const loadImage = async () => {
      if (!plan) { setImageUrl(""); return; }
      const token = localStorage.getItem("eduvigia_token");
      const response = await fetch(`${API_URL}${plan.image_url}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
      if (!response.ok) { setMessage("Não foi possível carregar a imagem da planta."); return; }
      const blob = await response.blob();
      if (revoked) return;
      localUrl = URL.createObjectURL(blob); setImageUrl(localUrl);
    };
    loadImage();
    return () => { revoked = true; if (localUrl) URL.revokeObjectURL(localUrl); };
  }, [activeId, plans]);

  const uploadPlan = async (event) => {
    event.preventDefault();
    if (!form.file || !schoolId) { setMessage("Selecione a escola e a imagem da planta."); return; }
    setUploading(true);
    try {
      const data = new FormData();
      data.append("school_id", schoolId); data.append("name", form.name);
      data.append("building", form.building); data.append("floor_label", form.floor_label); data.append("file", form.file);
      const created = await api("/floor-plans", { method: "POST", body: data });
      setForm({ name: "", building: "", floor_label: "", file: null });
      const input = document.getElementById("floor-plan-file"); if (input) input.value = "";
      await loadPlans(created.id); setMessage("Planta cadastrada com sucesso.");
    } catch (error) { setMessage(error.message); } finally { setUploading(false); }
  };

  const placeCamera = (event) => {
    if (!canWrite || !selectedCameraId || !activePlan) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const x = Math.max(0, Math.min(100, ((event.clientX - rect.left) / rect.width) * 100));
    const y = Math.max(0, Math.min(100, ((event.clientY - rect.top) / rect.height) * 100));
    const camera = schoolCameras.find((item) => Number(item.id) === Number(selectedCameraId));
    setPlacements((current) => {
      const existing = current.find((item) => Number(item.camera_id) === Number(selectedCameraId));
      if (existing) return current.map((item) => Number(item.camera_id) === Number(selectedCameraId) ? { ...item, x_percent: x, y_percent: y } : item);
      return [...current, { camera_id: Number(selectedCameraId), x_percent: x, y_percent: y, rotation_deg: 0, label: camera?.name || "" }];
    });
  };

  const savePlacements = async () => {
    if (!activePlan) return;
    try {
      const updated = await api(`/floor-plans/${activePlan.id}/cameras`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ placements: placements.map(({ camera_id, x_percent, y_percent, rotation_deg = 0, label = null }) => ({ camera_id, x_percent, y_percent, rotation_deg, label })) }),
      });
      setPlans((current) => current.map((item) => item.id === updated.id ? updated : item));
      setPlacements(updated.placements || []); setMessage("Posições salvas.");
    } catch (error) { setMessage(error.message); }
  };

  const deletePlan = async () => {
    if (!activePlan || !window.confirm("Excluir esta planta baixa?")) return;
    try { await api(`/floor-plans/${activePlan.id}`, { method: "DELETE" }); await loadPlans(); setMessage("Planta excluída."); }
    catch (error) { setMessage(error.message); }
  };

  const rotate = (cameraId, delta) => setPlacements((current) => current.map((item) => Number(item.camera_id) === Number(cameraId) ? { ...item, rotation_deg: Number(item.rotation_deg || 0) + delta } : item));
  const removePlacement = (cameraId) => setPlacements((current) => current.filter((item) => Number(item.camera_id) !== Number(cameraId)));

  return (
    <Page title="Plantas Baixas" subtitle="Posicionamento operacional de câmeras e sensores por escola, prédio e andar">
      {message && <div className="notice">{message}</div>}
      <div className="floorPlanToolbar">
        <Field label="Escola"><select value={schoolId} onChange={(event) => setSchoolId(event.target.value)}>{schools.map((school) => <option key={school.id} value={school.id}>{school.name}</option>)}</select></Field>
        <Field label="Planta"><select value={activeId} onChange={(event) => setActiveId(event.target.value)}><option value="">Selecione</option>{plans.map((plan) => <option key={plan.id} value={plan.id}>{plan.name}{plan.floor_label ? ` · ${plan.floor_label}` : ""}</option>)}</select></Field>
        {activePlan && <button type="button" onClick={() => onNavigate("monitor")}><Video size={16}/> Monitoramento</button>}
        {canWrite && activePlan && <button type="button" className="dangerButton" onClick={deletePlan}><Trash2 size={16}/> Excluir planta</button>}
      </div>

      {canWrite && <form className="floorPlanUpload" onSubmit={uploadPlan}>
        <Field label="Nome"><input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Ex.: Bloco principal" /></Field>
        <Field label="Prédio/Bloco"><input value={form.building} onChange={(e) => setForm({ ...form, building: e.target.value })} /></Field>
        <Field label="Andar/Pavimento"><input value={form.floor_label} onChange={(e) => setForm({ ...form, floor_label: e.target.value })} placeholder="Ex.: Térreo" /></Field>
        <Field label="Imagem da planta"><input id="floor-plan-file" type="file" accept="image/png,image/jpeg,image/webp" required onChange={(e) => setForm({ ...form, file: e.target.files?.[0] || null })} /></Field>
        <button className="primaryButton" disabled={uploading} type="submit"><Plus size={16}/>{uploading ? " Enviando..." : " Cadastrar planta"}</button>
      </form>}

      {!activePlan ? <div className="monitorEmpty"><FileImage size={32}/><b>Nenhuma planta selecionada</b><span>Cadastre JPG, PNG ou WebP de até 15 MB.</span></div> : (
        <div className="floorPlanWorkspace">
          <aside className="floorPlanSide">
            <h3>{activePlan.name}</h3><span>{activePlan.building || "Prédio não informado"} · {activePlan.floor_label || "Pavimento não informado"}</span>
            {canWrite && <><Field label="Câmera/sensor para posicionar"><select value={selectedCameraId} onChange={(e) => setSelectedCameraId(e.target.value)}><option value="">Selecione uma câmera</option>{schoolCameras.map((camera) => <option key={camera.id} value={camera.id}>{camera.name}{camera.device_id ? ` · CH${camera.logical_channel} · ${camera.sensor_type}` : ""}</option>)}</select></Field><small>Selecione a câmera e clique sobre a planta para posicioná-la ou reposicioná-la.</small></>}
            <div className="floorPlanPlacementList">{placements.map((item) => <div key={item.camera_id}><span className={`floorPlanStatus ${String(item.status || "PENDING").toLowerCase()}`}/><div><b>{item.camera_name || item.label || `Câmera #${item.camera_id}`}</b><span>{item.logical_channel ? `CH${item.logical_channel} · ${item.sensor_type || "GENERIC"}` : "Canal cadastrado"}</span></div>{canWrite && <><button type="button" onClick={() => rotate(item.camera_id, -15)}>↺</button><button type="button" onClick={() => rotate(item.camera_id, 15)}>↻</button><button type="button" onClick={() => removePlacement(item.camera_id)}><Trash2 size={14}/></button></>}</div>)}</div>
            {canWrite && <button type="button" className="primaryButton" onClick={savePlacements}><CheckCircle2 size={16}/> Salvar posições</button>}
          </aside>
          <section className={`floorPlanCanvas ${canWrite && selectedCameraId ? "placing" : ""}`} onClick={placeCamera}>
            {imageUrl ? <img src={imageUrl} alt={`Planta ${activePlan.name}`} draggable="false" /> : <div className="monitorEmpty">Carregando planta...</div>}
            {imageUrl && placements.map((item) => <button key={item.camera_id} type="button" className={`floorPlanCameraMarker ${String(item.status || "PENDING").toLowerCase()}`} style={{ left: `${item.x_percent}%`, top: `${item.y_percent}%`, transform: `translate(-50%,-50%) rotate(${item.rotation_deg || 0}deg)` }} title={`${item.camera_name || item.label} · ${item.sensor_type || "GENERIC"}`} onClick={(event) => { event.stopPropagation(); setSelectedCameraId(String(item.camera_id)); }}><Camera size={19}/><span>{item.camera_name || item.label}</span></button>)}
          </section>
        </div>
      )}
    </Page>
  );
}


function VideoWallPage({ cameras = [], schools = [], canWrite = false }) {
  const [layouts, setLayouts] = useState([]);
  const [activeId, setActiveId] = useState("");
  const [name, setName] = useState("Central 1");
  const [gridSize, setGridSize] = useState(4);
  const [qualityMode, setQualityMode] = useState("AUTO");
  const [slots, setSlots] = useState([null, null, null, null]);
  const [schoolFilter, setSchoolFilter] = useState("");
  const [message, setMessage] = useState("");

  const schoolMap = useMemo(() => Object.fromEntries(schools.map((school) => [String(school.id), school.name])), [schools]);
  const availableCameras = useMemo(() => cameras.filter((camera) => !schoolFilter || Number(camera.school_id) === Number(schoolFilter)), [cameras, schoolFilter]);
  const activeLayout = layouts.find((layout) => String(layout.id) === String(activeId));

  const loadLayouts = async (preferredId = null) => {
    const rows = await api("/video-wall/layouts");
    setLayouts(rows || []);
    const preferred = preferredId ? rows.find((row) => Number(row.id) === Number(preferredId)) : rows.find((row) => row.is_default) || rows[0];
    if (preferred) applyLayout(preferred);
  };

  const applyLayout = (layout) => {
    setActiveId(String(layout.id)); setName(layout.name); setGridSize(layout.grid_size); setQualityMode(layout.quality_mode || "AUTO");
    setSlots([...(layout.camera_ids || [])].slice(0, layout.grid_size).concat(Array(layout.grid_size).fill(null)).slice(0, layout.grid_size));
  };

  useEffect(() => { loadLayouts().catch((error) => setMessage(error.message)); }, []);

  const resizeGrid = (size) => {
    setGridSize(size);
    setSlots((current) => [...current, ...Array(size).fill(null)].slice(0, size));
  };
  const updateSlot = (index, value) => setSlots((current) => current.map((item, idx) => idx === index ? (value ? Number(value) : null) : item));
  const newLayout = () => { setActiveId(""); setName("Novo layout"); setGridSize(4); setQualityMode("AUTO"); setSlots([null,null,null,null]); setMessage(""); };
  const saveLayout = async () => {
    if (!canWrite) return;
    try {
      const payload={name:name.trim(),grid_size:gridSize,quality_mode:qualityMode,camera_ids:slots};
      const row=await api(activeId ? `/video-wall/layouts/${activeId}` : "/video-wall/layouts",{method:activeId?"PUT":"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
      setMessage("Layout salvo com sucesso."); await loadLayouts(row.id);
    } catch (error) { setMessage(error.message); }
  };
  const removeLayout = async () => {
    if (!activeId || !canWrite) return;
    if (!window.confirm("Excluir este layout do Video Wall?")) return;
    try { await api(`/video-wall/layouts/${activeId}`,{method:"DELETE"}); newLayout(); await loadLayouts(); setMessage("Layout excluído."); } catch(error){ setMessage(error.message); }
  };
  const setDefault = async () => {
    if (!activeId || !canWrite) return;
    try { const row=await api(`/video-wall/layouts/${activeId}/default`,{method:"POST"}); setMessage("Layout definido como padrão."); await loadLayouts(row.id); } catch(error){ setMessage(error.message); }
  };
  const fullscreen = () => document.getElementById("video-wall-stage")?.requestFullscreen?.();
  const effectiveProfile = qualityMode === "AUTO" ? (gridSize === 1 ? "MAIN" : "SUB") : qualityMode;

  return (
    <Page title="Video Wall Operacional" subtitle="Layouts persistentes para a central, com canais ópticos e térmicos tratados de forma independente">
      <div className="videoWallShell">
        <aside className="videoWallSidebar">
          <div className="cardHeader"><div><h3>Layouts</h3><span>{layouts.length} salvo(s)</span></div>{canWrite && <button type="button" onClick={newLayout}><Plus size={15}/> Novo</button>}</div>
          <div className="videoWallLayoutList">
            {layouts.map((layout)=><button type="button" key={layout.id} className={String(layout.id)===String(activeId)?"active":""} onClick={()=>applyLayout(layout)}><div><b>{layout.name}</b><span>Grade {layout.grid_size} · {layout.quality_mode}</span></div>{layout.is_default && <small>PADRÃO</small>}</button>)}
            {!layouts.length && <div className="monitorEmpty"><Video size={28}/><b>Nenhum layout salvo</b><span>Monte a grade e salve o primeiro Video Wall.</span></div>}
          </div>
        </aside>

        <section className="videoWallWorkspace">
          <div className="videoWallToolbar">
            <input value={name} onChange={(e)=>setName(e.target.value)} disabled={!canWrite} aria-label="Nome do layout" />
            <select value={gridSize} onChange={(e)=>resizeGrid(Number(e.target.value))} disabled={!canWrite}><option value={1}>1 câmera</option><option value={4}>2 × 2</option><option value={9}>3 × 3</option><option value={16}>4 × 4</option></select>
            <select value={qualityMode} onChange={(e)=>setQualityMode(e.target.value)} disabled={!canWrite}><option value="AUTO">AUTO</option><option value="SUB">SUB</option><option value="MAIN">MAIN</option></select>
            <select value={schoolFilter} onChange={(e)=>setSchoolFilter(e.target.value)}><option value="">Todas as escolas</option>{schools.map((school)=><option key={school.id} value={school.id}>{school.name}</option>)}</select>
            {canWrite && <button type="button" className="primaryButton" onClick={saveLayout}>Salvar</button>}
            {canWrite && activeId && <button type="button" onClick={setDefault}>Definir padrão</button>}
            {canWrite && activeId && <button type="button" onClick={removeLayout}><Trash2 size={15}/></button>}
            <button type="button" onClick={fullscreen}><Maximize2 size={15}/> Tela cheia</button>
          </div>
          {message && <div className="notice">{message}</div>}

          {canWrite && <div className={`videoWallSlotConfig config-${gridSize}`}>
            {slots.map((cameraId,index)=><label key={index}><span>Slot {index+1}</span><select value={cameraId || ""} onChange={(e)=>updateSlot(index,e.target.value)}><option value="">Vazio</option>{availableCameras.map((camera)=><option key={camera.id} value={camera.id} disabled={slots.some((id,idx)=>idx!==index && Number(id)===Number(camera.id))}>{schoolMap[String(camera.school_id)] || `Escola #${camera.school_id}`} · {camera.name}{camera.device_id ? ` · CH${camera.logical_channel} ${camera.sensor_type || ""}` : ""}</option>)}</select></label>)}
          </div>}

          <div id="video-wall-stage" className={`videoWallStage wall-${gridSize}`}>
            {slots.map((cameraId,index)=>{
              const camera=cameras.find((item)=>Number(item.id)===Number(cameraId));
              return <article className="videoWallTile" key={index}>{camera ? <><div className="videoWallVideo"><SecureStreamFrame cameraId={camera.id} profile={effectiveProfile} title={`Video Wall ${camera.name}`}/></div><div className="videoWallCaption"><div><b>{camera.name}</b><span>{schoolMap[String(camera.school_id)] || `Escola #${camera.school_id}`}{camera.device_id ? ` · CH${camera.logical_channel} · ${camera.sensor_type}` : ""}</span></div><small>{effectiveProfile}</small></div></> : <div className="videoWallEmpty"><Video size={32}/><b>Slot {index+1}</b><span>Sem câmera</span></div>}</article>;
            })}
          </div>
          <div className="videoWallFooter"><span>{activeLayout?.is_default ? "Layout padrão" : activeId ? "Layout salvo" : "Layout não salvo"}</span><span>{slots.filter(Boolean).length}/{gridSize} canais · Perfil {effectiveProfile}</span></div>
        </section>
      </div>
    </Page>
  );
}


function PlaybackPage({ cameras = [], schools = [], occurrences = [], canExport = false }) {
  const now = new Date();
  const oneHourAgo = new Date(now.getTime() - 60 * 60 * 1000);
  const toLocalInput = (value) => {
    const d = new Date(value.getTime() - value.getTimezoneOffset() * 60000);
    return d.toISOString().slice(0, 16);
  };
  const [cameraId, setCameraId] = useState(cameras[0]?.id ? String(cameras[0].id) : "");
  const [startAt, setStartAt] = useState(toLocalInput(oneHourAgo));
  const [endAt, setEndAt] = useState(toLocalInput(now));
  const [segments, setSegments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");
  const [previewUrl, setPreviewUrl] = useState("");
  const [lastEvidence, setLastEvidence] = useState(null);
  const [occurrenceId, setOccurrenceId] = useState("");

  useEffect(() => {
    if (!cameraId && cameras[0]?.id) setCameraId(String(cameras[0].id));
  }, [cameras, cameraId]);

  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl); }, [previewUrl]);

  const selectedCamera = cameras.find((item) => String(item.id) === String(cameraId));
  const schoolName = (id) => schools.find((item) => Number(item.id) === Number(id))?.name || `Escola #${id}`;
  const iso = (value) => new Date(value).toISOString();

  const searchPlayback = async () => {
    if (!cameraId) return;
    setLoading(true); setStatus("Consultando gravações no equipamento..."); setSegments([]);
    try {
      const result = await api(`/cameras/${cameraId}/playback/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ start_at: iso(startAt), end_at: iso(endAt), max_results: 100 }),
      });
      setSegments(result.segments || []);
      setStatus(`${result.count || 0} trecho(s) localizado(s).`);
    } catch (error) { setStatus(error.message); }
    finally { setLoading(false); }
  };

  const getBlob = async (path) => {
    const token = localStorage.getItem("eduvigia_token");
    const response = await fetch(`${API_URL}${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || `Falha HTTP ${response.status}`);
    }
    return response.blob();
  };

  const preview = async (segment) => {
    setLoading(true); setStatus("Preparando trecho temporário para revisão...");
    try {
      const start = new Date(segment.start_at);
      const naturalEnd = new Date(segment.end_at);
      const maxEnd = new Date(start.getTime() + 120000);
      const end = naturalEnd > maxEnd ? maxEnd : naturalEnd;
      const result = await api(`/cameras/${cameraId}/playback/preview`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ start_at: start.toISOString(), end_at: end.toISOString(), max_results: 1 }),
      });
      const blob = await getBlob(`/playback/previews/${result.token}`);
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      setPreviewUrl(URL.createObjectURL(blob));
      setStatus(`Pré-visualização pronta (${result.duration_seconds}s).`);
    } catch (error) { setStatus(error.message); }
    finally { setLoading(false); }
  };

  const exportEvidence = async (segment) => {
    if (!canExport) return;
    setLoading(true); setStatus("Exportando evidência forense...");
    try {
      const result = await api(`/cameras/${cameraId}/playback/export`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          start_at: new Date(segment.start_at).toISOString(),
          end_at: new Date(segment.end_at).toISOString(),
          occurrence_id: occurrenceId ? Number(occurrenceId) : null,
          observation: "Exportação via Playback EduVigIA",
        }),
      });
      setLastEvidence(result);
      setStatus(`Evidência #${result.id} criada e selada com SHA-256.`);
    } catch (error) { setStatus(error.message); }
    finally { setLoading(false); }
  };

  const verifyEvidence = async () => {
    if (!lastEvidence) return;
    try {
      const result = await api(`/evidence/${lastEvidence.id}/verify`);
      setLastEvidence((current) => ({ ...current, integrity_status: result.integrity_status }));
      setStatus(`Integridade: ${result.integrity_status}.`);
    } catch (error) { setStatus(error.message); }
  };

  const downloadEvidence = async () => {
    if (!lastEvidence) return;
    try {
      const blob = await getBlob(`/evidence/${lastEvidence.id}/file`);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a"); link.href = url; link.download = lastEvidence.original_name || lastEvidence.filename || `evidence-${lastEvidence.id}.mp4`;
      document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(url);
    } catch (error) { setStatus(error.message); }
  };

  return (
    <Page title="Playback e Evidências" subtitle="Pesquisa de gravações por canal lógico, revisão sob demanda e exportação forense">
      <div className="playbackLayout">
        <section className="dataCard playbackSearchCard">
          <div className="cardHeader"><h2>Pesquisa de gravações</h2><span>Hikvision RTSP / ISAPI</span></div>
          <div className="playbackFilters">
            <label><span>Câmera / sensor</span><select value={cameraId} onChange={(e) => setCameraId(e.target.value)}><option value="">Selecione</option>{cameras.map((camera) => <option key={camera.id} value={camera.id}>{schoolName(camera.school_id)} · {camera.name} · CH{camera.logical_channel || 1} {camera.sensor_type || "VISIBLE"}</option>)}</select></label>
            <label><span>Início</span><input type="datetime-local" value={startAt} onChange={(e) => setStartAt(e.target.value)} /></label>
            <label><span>Fim</span><input type="datetime-local" value={endAt} onChange={(e) => setEndAt(e.target.value)} /></label>
            <button type="button" className="primaryButton" disabled={!cameraId || loading} onClick={searchPlayback}><Search size={16} /> {loading ? "Processando..." : "Buscar gravações"}</button>
          </div>
          {selectedCamera && <div className="playbackCameraMeta"><b>{selectedCamera.name}</b><span>{schoolName(selectedCamera.school_id)} · {selectedCamera.location} · Canal {selectedCamera.logical_channel || 1} · {selectedCamera.sensor_type || "VISIBLE"}</span></div>}
          {status && <div className="notice">{status}</div>}
        </section>

        <section className="dataCard playbackResultsCard">
          <div className="cardHeader"><h2>Timeline encontrada</h2><span>{segments.length} trecho(s)</span></div>
          {segments.length === 0 ? <Empty text="Faça uma pesquisa para consultar as gravações disponíveis no NVR/câmera." /> : (
            <div className="playbackSegments">
              {segments.map((segment, index) => (
                <article key={`${segment.start_at}-${index}`}>
                  <div className="playbackSegmentIcon"><FileVideo size={22} /></div>
                  <div className="playbackSegmentInfo"><b>{new Date(segment.start_at).toLocaleString("pt-BR")} → {new Date(segment.end_at).toLocaleTimeString("pt-BR")}</b><span>{segment.record_type || "CONTINUOUS"}</span></div>
                  <div className="playbackSegmentActions">
                    <button type="button" disabled={loading} onClick={() => preview(segment)}><Eye size={15} /> Revisar</button>
                    {canExport && <button type="button" disabled={loading} onClick={() => exportEvidence(segment)}><Fingerprint size={15} /> Evidência</button>}
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>

        {previewUrl && <section className="dataCard playbackPreviewCard"><div className="cardHeader"><h2>Revisão do trecho</h2><span>temporária</span></div><video src={previewUrl} controls autoPlay playsInline /></section>}

        {canExport && <section className="dataCard playbackEvidenceCard">
          <div className="cardHeader"><h2>Vínculo forense</h2><span>SHA-256 + cadeia de custódia</span></div>
          <label><span>Ocorrência (opcional)</span><select value={occurrenceId} onChange={(e) => setOccurrenceId(e.target.value)}><option value="">Sem ocorrência vinculada</option>{occurrences.filter((item) => !selectedCamera || !item.school_id || Number(item.school_id) === Number(selectedCamera.school_id)).map((item) => <option key={item.id} value={item.id}>{item.protocol} · {item.school_name}</option>)}</select></label>
          {lastEvidence && <div className="forensicSeal"><ShieldCheck size={28} /><div><b>Evidência #{lastEvidence.id} · {lastEvidence.integrity_status}</b><span>SHA-256: {lastEvidence.sha256}</span><small>{lastEvidence.file_size_bytes || 0} bytes · CH{lastEvidence.logical_channel || 1} · {lastEvidence.sensor_type}</small></div><div className="forensicActions"><button onClick={verifyEvidence}>Verificar hash</button><button onClick={downloadEvidence}><Download size={15} /> Baixar</button></div></div>}
        </section>}
      </div>
    </Page>
  );
}

function HomologationPage({ data, checklist, onRefresh, onFeedback }) {
  const statusClass = (status) => {
    if (status === "APROVADO") return "success";
    if (status === "FALHOU") return "danger";
    if (status === "PENDENTE") return "warning";
    return "neutral";
  };

  if (!data) {
    return (
      <Page title="Homologação" subtitle="Diagnóstico técnico do ambiente">
        <div className="dataCard">
          <Empty text="Diagnóstico indisponível ou perfil sem permissão." />
        </div>
      </Page>
    );
  }

  return (
    <Page title="Homologação" subtitle="Testes, requisitos e preparação para a v2.0.0">
      <div className="homologationHeader">
        <div><span>Versão</span><b>{data.version}</b></div>
        <div><span>Resultado geral</span><b>{checklist?.overall || "PENDENTE"}</b></div>
        <div><span>Última verificação</span><b>{new Date(data.checked_at).toLocaleString("pt-BR")}</b></div>
        <button type="button" onClick={async () => {
          const ok = await onRefresh?.();
          onFeedback?.(ok === false ? "error" : "success", ok === false ? "Falha ao atualizar homologação" : "Diagnóstico de homologação atualizado", ok === false ? "Não foi possível sincronizar o checklist." : "Checklist e estado técnico sincronizados.");
        }}><RefreshCw size={16} />Atualizar diagnóstico</button>
      </div>

      {checklist && (
        <>
          <div className="homologationSummary">
            <article><span>Aprovados</span><b>{checklist.summary.approved}</b></article>
            <article><span>Pendentes</span><b>{checklist.summary.pending}</b></article>
            <article><span>Falhas</span><b>{checklist.summary.failed}</b></article>
            <article><span>Total</span><b>{checklist.summary.total}</b></article>
          </div>

          <section className="dataCard homologationChecklist">
            <div className="cardHeader"><h2>Checklist para v2.0.0</h2><span>{checklist.checks.length}</span></div>
            <div className="checklistRows">
              {checklist.checks.map((item) => (
                <article key={item.code}>
                  <CheckCircle2 size={19} />
                  <div><b>{item.title}</b><span>{item.detail}</span></div>
                  <span className={`statusPill ${statusClass(item.status)}`}>
                    {item.status.replaceAll("_", " ")}
                  </span>
                </article>
              ))}
            </div>
          </section>
        </>
      )}

      <div className="homologationGrid">
        <section className="dataCard">
          <div className="cardHeader"><h2>Serviços</h2></div>
          {Object.entries(data.services || {}).map(([name, service]) => (
            <div className="healthLine" key={name}>
              <span>{name.replaceAll("_", " ")}</span>
              <b className={service.status === "ONLINE" ? "serviceOnline" : "serviceOffline"}>{service.status}</b>
            </div>
          ))}
        </section>

        <section className="dataCard">
          <div className="cardHeader"><h2>Câmeras</h2></div>
          <div className="diagnosticMetric"><span>Total</span><b>{data.cameras.total}</b></div>
          <div className="diagnosticMetric"><span>Online</span><b>{data.cameras.online}</b></div>
          <div className="diagnosticMetric"><span>Offline</span><b>{data.cameras.offline}</b></div>
          <div className="diagnosticMetric"><span>Com stream</span><b>{data.cameras.provisioned}</b></div>
        </section>

        <section className="dataCard">
          <div className="cardHeader"><h2>Portas</h2></div>
          {Object.entries(data.ports || {}).map(([name, port]) => (
            <div className="healthLine" key={name}><span>{name}</span><b>{port}</b></div>
          ))}
        </section>

        <section className="dataCard full">
          <div className="cardHeader"><h2>MediaMTX</h2></div>
          <pre className="diagnosticJson">{JSON.stringify(data.video, null, 2)}</pre>
        </section>
      </div>
    </Page>
  );
}

function DetailModal({ title, onClose, children }) {
  return (
    <div className="modalBackdrop" onMouseDown={onClose}>
      <div className="detailModal" onMouseDown={(event) => event.stopPropagation()}>
        <div className="modalHeader">
          <h2>{title}</h2>
          <button onClick={onClose}>Fechar</button>
        </div>
        <div className="modalBody">{children}</div>
      </div>
    </div>
  );
}

function PlaceholderPage({ icon: Icon, title, text }) {
  return (
    <Page title={title} subtitle={text}>
      <div className="placeholder">
        <Icon size={56} />
        <h2>Módulo preparado</h2>
        <p>Esta área seguirá o mesmo padrão visual e será ativada na próxima fase.</p>
      </div>
    </Page>
  );
}

function priorityLabel(value) {
  return {
    CRITICA: "Crítica",
    ALTA: "Alta",
    MEDIA: "Média",
    BAIXA: "Baixa",
  }[value] || value;
}

