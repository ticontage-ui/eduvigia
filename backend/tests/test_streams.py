from app.services.hikvision import stream_channel_id


def test_hikvision_stream_ids():
    assert stream_channel_id(1, "MAIN") == 101
    assert stream_channel_id(1, "SUB") == 102
    assert stream_channel_id(16, "MAIN") == 1601
    assert stream_channel_id(16, "SUB") == 1602
