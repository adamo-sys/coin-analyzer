# First Phone Entry Demo

Use a trusted private LAN only. Do not port-forward, publish the address, or disable firewall/security controls.

1. On the PC, choose a **test** collection path and an empty private state folder, then run:
   `C:\Projects\coin-analyzer\.venv\Scripts\python.exe phone_entry_demo.py --lan-host <PC-private-IPv4> --collection <test-collection.json> --state-root <private-state-folder>`
2. A desktop-local dialog displays the only URL to open and a one-use pairing secret; the secret is not written to the terminal. On the iPhone connected to that same LAN, open the displayed `http://<PC-private-IPv4>:8765/` URL.
3. Enter the pairing secret within two minutes. Select/capture one **OBVERSE** and one **REVERSE** JPEG or PNG, create the draft, complete manual fields, press **HUMAN VERIFY**, then separately press **CONFIRM SAVE**.
4. Confirm the saved item ID and safe result page. The test entry is in the collection path supplied to the command; remove it later only through normal collection controls.
5. Press `Ctrl+C` on the PC when finished. This stops the listener and revokes the pairing/session immediately. Confirm the phone can no longer access the page.

The first real-device test is limited to the explicitly approved constrained trusted-LAN HTTP posture. It has no recognition, cloud sync, public access, or multi-user behavior.
