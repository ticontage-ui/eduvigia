# EduVigIA Emergency Chat — Attachments Contract

Version: 0.4.0-R1

## Allowed types

- JPG / JPEG
- PNG
- WEBP
- PDF
- DOC / DOCX
- XLS / XLSX
- TXT
- CSV

## Limits

- 25 MB maximum per file
- 5 files maximum per message
- 50 MB maximum combined per message

## Security rules

1. School isolation remains mandatory.
2. An attachment belongs to exactly one emergency channel.
3. Download requires authorization to that channel.
4. A school cannot download attachments from another school's channel.
5. File extension and MIME type are allowlisted.
6. Binary signatures are validated for images, PDF and Office documents.
7. Uploaded filenames are sanitized.
8. Stored filenames are randomized.
9. SHA-256 is recorded for every attachment.
10. Executables and scripts are not allowed.

## Malware scanning

V0.4.0 performs type/signature validation but does not yet claim antivirus scanning.
A malware-scanning gate must be added before production release.