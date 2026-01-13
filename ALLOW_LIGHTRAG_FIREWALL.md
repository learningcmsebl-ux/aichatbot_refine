# Allow LightRAG Port 9262 in Windows Firewall

This guide will help you allow port 9262 in Windows Firewall so that LightRAG can be accessed from remote PCs.

## Method 1: Run PowerShell Script as Administrator (Recommended)

1. **Right-click** on PowerShell
2. Select **"Run as Administrator"**
3. Navigate to the project directory:
   ```powershell
   cd E:\Chatbot_refine
   ```
4. Run the script:
   ```powershell
   .\allow_lightrag_firewall.ps1
   ```

## Method 2: Manual Windows Firewall Configuration

1. Press `Win + R` to open Run dialog
2. Type `wf.msc` and press Enter (opens Windows Defender Firewall with Advanced Security)
3. Click **"Inbound Rules"** in the left panel
4. Click **"New Rule..."** in the right panel
5. Select **"Port"** and click Next
6. Select **"TCP"** and enter **9262** in "Specific local ports"
7. Click Next
8. Select **"Allow the connection"**
9. Click Next
10. Check all profiles (Domain, Private, Public)
11. Click Next
12. Name it: **"LightRAG Port 9262"**
13. Click Finish

## Method 3: Using Command Prompt (as Administrator)

1. Open **Command Prompt as Administrator**
2. Run:
   ```cmd
   netsh advfirewall firewall add rule name="LightRAG Port 9262" dir=in action=allow protocol=TCP localport=9262
   ```

## Verify the Rule

After adding the rule, verify it exists:

```powershell
Get-NetFirewallRule -DisplayName "LightRAG Port 9262" | Select-Object DisplayName, Enabled, Direction, Action
```

## Important Notes

1. **LightRAG Configuration**: Make sure LightRAG is configured to listen on `0.0.0.0` (all interfaces) and not just `127.0.0.1` (localhost only). If it's only listening on localhost, remote connections won't work even with the firewall rule.

2. **Check LightRAG Binding**: Verify LightRAG is listening on all interfaces:
   ```powershell
   netstat -ano | findstr :9262
   ```
   You should see `0.0.0.0:9262` or `[::]:9262` (not just `127.0.0.1:9262`)

3. **Network Profile**: The firewall rule should be enabled for the network profile you're using (Domain, Private, or Public).

4. **Remote Access**: After adding the rule, remote PCs should be able to access LightRAG at:
   ```
   http://YOUR_IP_ADDRESS:9262
   ```
   Replace `YOUR_IP_ADDRESS` with your computer's IP address (find it with `ipconfig`).

## Troubleshooting

- **Still can't connect?** Check if LightRAG is listening on `0.0.0.0` and not just `127.0.0.1`
- **Firewall rule not working?** Make sure it's enabled and applies to your current network profile
- **Need to remove the rule?** Run: `Remove-NetFirewallRule -DisplayName "LightRAG Port 9262"`

