# Firewall Setup for Admin Panel (Port 8009)

To allow remote access to the Fee Engine Admin Panel, you need to add a Windows Firewall rule for port 8009.

## ⚠️ Important: Administrator Privileges Required

All methods below require running as Administrator.

## Method 1: Using the Provided Scripts (Easiest)

### Option A: PowerShell Script
1. Right-click `add_firewall_rule.ps1`
2. Select "Run with PowerShell" (or "Run as Administrator")
3. If prompted, allow the script to run

### Option B: Batch File
1. Right-click `add_firewall_rule.bat`
2. Select "Run as administrator"
3. Follow the prompts

## Method 2: Manual PowerShell Command

1. Open PowerShell as Administrator:
   - Press `Win + X`
   - Select "Windows PowerShell (Admin)" or "Terminal (Admin)"

2. Run this command:
```powershell
New-NetFirewallRule -DisplayName "Fee Engine Admin Panel (Port 8009)" -Direction Inbound -LocalPort 8009 -Protocol TCP -Action Allow -Description "Allow inbound traffic for Fee Engine Admin Panel on port 8009"
```

## Method 3: Using netsh Command

1. Open Command Prompt as Administrator:
   - Press `Win + X`
   - Select "Command Prompt (Admin)" or "Terminal (Admin)"

2. Run this command:
```cmd
netsh advfirewall firewall add rule name="Fee Engine Admin Panel (Port 8009)" dir=in action=allow protocol=TCP localport=8009
```

## Method 4: Using Windows Firewall GUI

1. Open Windows Defender Firewall:
   - Press `Win + R`
   - Type `wf.msc` and press Enter

2. Click "Inbound Rules" in the left panel

3. Click "New Rule..." in the right panel

4. Rule Type: Select "Port" → Next

5. Protocol and Ports:
   - Select "TCP"
   - Select "Specific local ports"
   - Enter: `8009`
   - Click Next

6. Action: Select "Allow the connection" → Next

7. Profile: Select all (Domain, Private, Public) → Next

8. Name: Enter "Fee Engine Admin Panel (Port 8009)" → Finish

## Verify the Rule

### Using PowerShell:
```powershell
Get-NetFirewallRule -DisplayName "*Fee Engine Admin Panel*"
```

### Using netsh:
```cmd
netsh advfirewall firewall show rule name="Fee Engine Admin Panel (Port 8009)"
```

### Using GUI:
- Open Windows Defender Firewall → Inbound Rules
- Look for "Fee Engine Admin Panel (Port 8009)"

## Access from Remote Computer

Once the firewall rule is added, you can access the admin panel from any computer on the network:

```
http://<your-server-ip>:8009
```

Replace `<your-server-ip>` with the IP address of the computer running the Docker container.

### Find Your IP Address

**Windows:**
```cmd
ipconfig
```
Look for "IPv4 Address" under your active network adapter.

**PowerShell:**
```powershell
Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -notlike "127.*"} | Select-Object IPAddress
```

## Security Considerations

⚠️ **Important Security Notes:**

1. **Change Default Credentials**: Before exposing to the network, change the default admin username and password in `docker-compose.yml`

2. **Use HTTPS in Production**: For production deployments, use a reverse proxy (nginx, Apache) with SSL/TLS certificates

3. **Restrict Access**: Consider restricting the firewall rule to specific IP addresses or subnets if possible

4. **Network Security**: Ensure your network is secure and only trusted users can access port 8009

5. **Monitor Access**: Regularly check logs for unauthorized access attempts

## Remove the Firewall Rule (if needed)

### Using PowerShell:
```powershell
Remove-NetFirewallRule -DisplayName "Fee Engine Admin Panel (Port 8009)"
```

### Using netsh:
```cmd
netsh advfirewall firewall delete rule name="Fee Engine Admin Panel (Port 8009)"
```

### Using GUI:
- Open Windows Defender Firewall → Inbound Rules
- Find the rule and right-click → Delete

## Troubleshooting

### Cannot access from remote computer

1. **Verify firewall rule exists**: Use the verification commands above
2. **Check Docker port mapping**: Ensure `8009:8009` is mapped in docker-compose.yml
3. **Check container is running**: `docker ps | grep fee-engine-admin`
4. **Test locally first**: Try `http://localhost:8009` on the server
5. **Check Windows Firewall status**: Ensure Windows Firewall is not blocking the connection
6. **Check network firewall**: If behind a corporate firewall, contact IT to open port 8009
7. **Verify IP address**: Make sure you're using the correct server IP address

### Port already in use

If port 8009 is already in use by another application:
1. Change the port in `docker-compose.yml`:
   ```yaml
   ports:
     - "8010:8009"  # Use 8010 externally, 8009 internally
   ```
2. Update the firewall rule to use the new external port
3. Rebuild and restart: `docker-compose up -d --build fee-engine-admin`









