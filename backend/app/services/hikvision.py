"""Serviço Hikvision/ISAPI.

A implementação funcional permanece integrada à aplicação nesta versão para
preservar compatibilidade. Este módulo documenta o contrato que será isolado
integralmente na próxima etapa de segurança e testes.
"""

DEVICE_INFO_PATH = "/ISAPI/System/deviceInfo"
INPUT_PROXY_CHANNELS_PATH = "/ISAPI/ContentMgmt/InputProxy/channels"
VIDEO_INPUT_CHANNELS_PATH = "/ISAPI/System/Video/inputs/channels"


def stream_channel_id(channel: int, profile: str) -> int:
    suffix = 2 if profile.upper() == "SUB" else 1
    return int(channel) * 100 + suffix
