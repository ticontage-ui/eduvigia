from app.application import Camera, VideoDevice, VideoDeviceIn, VideoDeviceChannelIn, build_camera_rtsp


def main() -> None:
    required_camera_fields = {"device_id", "logical_channel", "sensor_type", "sensor_label", "primary_sensor"}
    camera_fields = set(Camera.__table__.columns.keys())
    device_fields = set(VideoDevice.__table__.columns.keys())
    required_device = {"school_id", "ip_address", "rtsp_port", "username", "password", "device_type", "channel_count"}
    assert required_camera_fields.issubset(camera_fields)
    assert required_device.issubset(device_fields)
    assert "BISPECTRUM" in VideoDeviceIn.model_fields["device_type"].annotation.__args__
    assert "THERMAL" in VideoDeviceChannelIn.model_fields["sensor_type"].annotation.__args__
    print("EDUVIGIA_F3R2_MULTICHANNEL_PREFLIGHT_OK")


if __name__ == "__main__":
    main()
