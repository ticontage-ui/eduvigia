"""Migração transacional de credenciais técnicas legadas do EduVigIA."""

import json

from .application import Camera, Recorder, SessionLocal, _fernet, encrypt_secret


def migrate() -> dict[str, int | bool]:
    if not _fernet():
        raise RuntimeError("EDUVIGIA_CREDENTIAL_KEY não está configurada ou é inválida")

    with SessionLocal() as db:
        try:
            updated_recorders = 0
            updated_cameras = 0

            for row in db.query(Recorder).filter(Recorder.password.isnot(None)).all():
                if row.password and not row.password.startswith("enc:v1:"):
                    row.password = encrypt_secret(row.password)
                    updated_recorders += 1

            for row in db.query(Camera).filter(Camera.password.isnot(None)).all():
                if row.password and not row.password.startswith("enc:v1:"):
                    row.password = encrypt_secret(row.password)
                    updated_cameras += 1

            db.commit()

            remaining = (
                db.query(Recorder)
                .filter(Recorder.password.isnot(None), ~Recorder.password.startswith("enc:v1:"))
                .count()
                + db.query(Camera)
                .filter(Camera.password.isnot(None), ~Camera.password.startswith("enc:v1:"))
                .count()
            )
            if remaining:
                raise RuntimeError(f"Ainda existem {remaining} credenciais técnicas sem criptografia")

            return {
                "ok": True,
                "updated_recorders": updated_recorders,
                "updated_cameras": updated_cameras,
                "remaining_plaintext": remaining,
            }
        except Exception:
            db.rollback()
            raise


if __name__ == "__main__":
    print(json.dumps(migrate(), ensure_ascii=False))
