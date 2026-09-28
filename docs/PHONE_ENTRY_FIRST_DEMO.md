# First Phone Entry Demo

Use a trusted private LAN only. Do not port-forward, publish the address, or disable firewall/security controls.

1. On the PC, choose a **test** collection path and an empty private state folder, then run:
   `C:\Projects\coin-analyzer\.venv\Scripts\python.exe phone_entry_demo.py --lan-host <PC-private-IPv4> --collection <test-collection.json> --state-root <private-state-folder>`
2. The PC first starts and verifies the private-LAN listener. It then shows a desktop-local QR code. With the iPhone connected to that same LAN, scan the QR code using the Camera app and open its local link. Do not photograph, transcribe, share, or manually type a credential. The QR carries one high-entropy bootstrap value that expires after two minutes, is exchanged immediately for the existing bounded browser session, and is not written to the terminal or retained in the browser URL after the redirect.
3. The iPhone opens the token-free capture page. Select/capture one **OBVERSE** and one **REVERSE** JPEG or PNG, then tap **CREATE DRAFT**. Ordinary current iPhone JPEG photos (including 12/24 MP camera photos) are supported: each image may be up to 16 MiB, the pair up to 32 MiB, with a decoded maximum of 30 MP and 8,000 pixels on either edge. HEIC/HEIF is intentionally not accepted; choose/capture a JPEG or PNG rather than manually resizing a normal JPEG. The host re-encodes accepted images to strip inbound metadata while preserving the bounded review image; it performs no recognition or cloud upload. Complete manual fields, press **HUMAN VERIFY**, then separately press **CONFIRM SAVE**.
4. Confirm the saved item ID and safe result page. The test entry is in the collection path supplied to the command; remove it later only through normal collection controls.
5. Press `Ctrl+C` on the PC when finished. This stops the listener and revokes the pairing/session immediately. Confirm the phone can no longer access the page.

The first real-device test is limited to the explicitly approved constrained trusted-LAN HTTP posture. The QR bootstrap is a short-lived bearer value: anyone who scans it before the intended phone could claim the one session, so keep the PC display private and stop the demo immediately if it is exposed. It has no recognition, cloud sync, public access, or multi-user behavior.
