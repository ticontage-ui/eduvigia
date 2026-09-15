# EduVigIA Chat â€” Emergency Channels Contract

Version: 0.3.0-R1

## Purpose

The Chat module is an institutional emergency communication channel.

It is not a general-purpose messenger.

## Communication rules

1. A school may communicate only inside its own emergency channel.
2. Schools may not communicate with other schools.
3. The Municipal Guard may access school emergency channels assigned by the system.
4. The Education Secretariat may access school emergency channels assigned by the system.
5. Users cannot create arbitrary conversations.
6. Users cannot choose arbitrary channel members.
7. Channel membership is system-managed.
8. School access is additionally validated by school_code at the API layer.
9. V0.3 supports text messages only.
10. Attachments, audio, voice messages, PTT, calls, video and media are out of scope.

## Current mock topology

- SCHOOL-A
  - Gestor Escola A
  - Guarda
  - Secretaria

- SCHOOL-B
  - Gestor Escola B
  - Guarda
  - Secretaria

School A cannot read or write SCHOOL-B.
School B cannot read or write SCHOOL-A.

## Core integration

Disabled in V0.3.

The module remains standalone and does not query or mutate the EduVigIA Core database.