# Lyrion Music Server (LMS) Integration for Unfolded Circle Remote 2/3

Control all your Squeezebox and compatible players connected to your Lyrion Music Server directly from your Unfolded Circle Remote 2 or Remote 3 with comprehensive multi-room audio control, **album artwork**, **rich metadata**, and **player grouping/synchronization**.

![LMS](https://img.shields.io/badge/LMS-Lyrion%20Music%20Server-orange)
[![GitHub Release](https://img.shields.io/github/v/release/mase1981/uc-intg-lmserver?style=flat-square)](https://github.com/mase1981/uc-intg-lmserver/releases)
![License](https://img.shields.io/badge/license-MPL--2.0-blue?style=flat-square)
[![GitHub issues](https://img.shields.io/github/issues/mase1981/uc-intg-lmserver?style=flat-square)](https://github.com/mase1981/uc-intg-lmserver/issues)
[![Community Forum](https://img.shields.io/badge/community-forum-blue?style=flat-square)](https://community.unfoldedcircle.com/)
[![Discord](https://badgen.net/discord/online-members/zGVYf58)](https://discord.gg/zGVYf58)
![GitHub Downloads (all assets, all releases)](https://img.shields.io/github/downloads/mase1981/uc-intg-lmserver/total?style=flat-square)
[![Buy Me A Coffee](https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=flat-square)](https://buymeacoffee.com/meirmiyara)
[![PayPal](https://img.shields.io/badge/PayPal-donate-blue.svg?style=flat-square)](https://paypal.me/mmiyara)
[![Github Sponsors](https://img.shields.io/badge/GitHub%20Sponsors-30363D?&logo=GitHub-Sponsors&logoColor=EA4AAA&style=flat-square)](https://github.com/sponsors/mase1981)


## Features

This integration provides (almost) full control of all players connected to your Lyrion Music Server (formerly Logitech Media Server) with rich media information display, multi-room synchronization, and favorites access directly from your Unfolded Circle Remote.

---
## ❤️ Support Development ❤️

If you find this integration useful, consider supporting development:

[![GitHub Sponsors](https://img.shields.io/badge/Sponsor-GitHub-pink?style=for-the-badge&logo=github)](https://github.com/sponsors/mase1981)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://www.buymeacoffee.com/meirmiyara)
[![PayPal](https://img.shields.io/badge/PayPal-00457C?style=for-the-badge&logo=paypal&logoColor=white)](https://paypal.me/mmiyara)

Your support helps maintain this integration. Thank you! ❤️
---

### 🎵 **Media Player Control**

#### **Playback Control**
- **Play/Pause Toggle** - Seamless playback control
- **Previous/Next Track** - Navigate through playlist
- **Stop** - Stop playback
- **Seek** - Jump to any position in track
- **Repeat Modes** - Off, One, All
- **Shuffle** - Toggle shuffle mode

#### **Volume Control**
- **Volume Up/Down** - Adjust volume levels
- **Set Volume** - Direct volume control (0-100)
- **Mute Toggle** - Quick mute/unmute
- **Individual Control** - Independent volume for each player

### 📺 **Rich Media Information Display**

#### **Dynamic Metadata**
Real-time display of media information from LMS:
- **Media Title** - Song/track title from LMS metadata
- **Artist** - Artist name from music library
- **Album** - Album name from music library
- **Album Artwork** - High-quality album art display via LMS HTTP interface
- **Progress Information** - Current position and total duration

### 🎛️ **Multi-Room Audio Control**

#### **Player Grouping/Synchronization**
- **Sync Players** - Group multiple players for synchronized playback
- **Unsync Players** - Remove players from sync groups
- **Visual Group Status** - See which players are grouped together
- **Perfect Sync** - < 1ms synchronization accuracy across all players

#### **Remote Control Entity**
Each player gets a dedicated remote control with: (must be preconfigured on server)
- **Grouping Page** - Quick access to sync/unsync all available players
- **Favorites Page** - One-touch access to your LMS favorites (up to 24)
- **Playlist Page** - Clear playlist, add random songs/albums
- **Sleep Timer** - 15, 30, 60, 90 minute timers or cancel

### 🎼 **Favorites Support** (must be preconfigured on server)

- **Automatic Discovery** - All LMS favorites loaded automatically during setup
- **Quick Access** - Up to 24 favorites on remote control page
- **One-Touch Playback** - Start favorite stations, playlists, or tracks instantly
- **Radio Stations** - Internet radio favorites supported
- **Playlists** - Saved playlist favorites supported

### 🔌 **Multi-Device Support**
- **Multiple Players** - Control unlimited Squeezebox and compatible players
- **Individual Configuration** - Each player gets media player + remote control entity
- **Player Discovery** - Automatic detection of all connected players
- **Unique Player Names** - Each player identified by name from LMS

### **LMS Requirements**
- **LMS Version**: 8.0.0 or higher (Lyrion Music Server recommended) (tested against Lyrion Music Server 9.0.3)
- **HTTP Interface**: Enabled by default on port 9000
- **Network Access**: LMS must be accessible on local network
- **Players**: At least one Squeezebox or compatible player connected

### **Compatible Players**
- **Squeezebox Hardware**: Touch, Radio, Boom, Classic, Transporter, Duet
- **Software Players**: Squeezelite (most common), SqueezePlay, SqueezeSlave
- **Modern Devices**: WiiM Pro/Pro Plus/Ultra/Amp, various audiophile streamers
- **Mobile Apps**: iPeng (iOS), Squeezer (Android), Orange Squeeze, and others

### **Network Requirements**
- **Local Network Access** - Integration requires same network as LMS server (Remote and server on same network)
- **HTTP Port** - Default 9000 (configurable)
- **CLI Port** - Default 9090 (configurable)
- **Firewall Configuration** - Ensure LMS all required ports are accessible

## Installation

### Option 1: Remote Web Interface (Recommended)
1. Navigate to the [**Releases**](https://github.com/mase1981/uc-intg-lmserver/releases) page
2. Download the latest `uc-intg-lmserver-<version>.tar.gz` file
3. Open your remote's web interface (`http://your-remote-ip`)
4. Go to **Settings** → **Integrations** → **Add Integration**
5. Click **Upload** and select the downloaded `.tar.gz` file

### Option 2: Docker (Advanced Users)

The integration is available as a pre-built Docker image from GitHub Container Registry:

**Image**: `ghcr.io/mase1981/uc-intg-lmserver:latest`

**Docker Compose:**
```yaml
services:
  uc-intg-lmserver:
    image: ghcr.io/mase1981/uc-intg-lmserver:latest
    container_name: uc-intg-lmserver
    network_mode: host
    volumes:
      - </local/path>:/data
    environment:
      - UC_CONFIG_HOME=/data
      - UC_INTEGRATION_HTTP_PORT=9090
    restart: unless-stopped
```

**Docker Run:**
```bash
docker run -d --name=uc-intg-lmserver --network host -v </local/path>:/data -e UC_CONFIG_HOME=/data -e UC_INTEGRATION_HTTP_PORT=9090 --restart unless-stopped ghcr.io/mase1981/uc-intg-lmserver:latest
```

## Configuration

### Step 1: Prepare Your LMS Server

**IMPORTANT**: Lyrion Music Server must be running and accessible before adding the integration.

#### Verify LMS is Running:
1. Open browser and visit: `http://YOUR_LMS_SERVER_IP:9000`
2. You should see the LMS web interface
3. Verify your players are visible in the player dropdown
4. Note the IP address of your LMS server

#### Check HTTP Interface:
- LMS HTTP interface is enabled by default on port 9000
- No password required (local network security)
- Test API access: `http://YOUR_LMS_SERVER_IP:9000/jsonrpc.js`

### Step 2: Setup Integration

1. After installation, go to **Settings** → **Integrations**
2. The LMS integration should appear in **Available Integrations**
3. Click **"Configure"** and follow the setup wizard:

   **Page 1 - Server Configuration:**
   - **LMS Server IP Address**: IP of device running LMS (e.g., 192.168.1.100)
   - **LMS Server Port**: LMS HTTP port (default: 9000)
   - Click **Next**

   **Page 2 - Player Discovery:**
   - Integration will automatically discover all connected players
   - Review list of discovered players
   - Select which players to add (checkboxes)
   - All connected players are auto-selected
   - Click **Complete Setup**

4. Integration will create **TWO entities per player**:
   - **Media Player**: `media_player.[player_name]` - Full playback control
   - **Remote Control**: `remote.[player_name]_control` - Grouping & favorites


## Using the Integration

### Media Player Entity

The media player entity provides standard music control with rich metadata:

- **Now Playing Display**: Title, artist, album, artwork
- **Playback Controls**: Play, pause, stop, next, previous
- **Volume Control**: Volume slider, mute toggle
- **Progress Bar**: Seek to any position in track
- **Repeat & Shuffle**: Toggle modes directly

### Remote Control Entity

The remote control entity provides advanced features across multiple pages:

#### **Playback Page** (Main)
- Play, Pause, Stop, Previous, Next controls
- Volume Up/Down, Mute
- Power On/Off controls
- Sleep timer buttons (15/30/60 min, cancel)

#### **Group Players Page**
- **UNGROUP** - Remove this player from any sync group
- **→ [Player Name]** - Sync this player with another player
- Visual buttons for all available players
- Instant multi-room audio grouping

#### **Favorites Page** (if favorites configured)
- Up to 24 favorite buttons on screen
- One-touch playback of favorite stations, playlists, tracks
- Button labels show favorite names (truncated to fit)
- Automatically populated from LMS favorites

#### **Playlist Page**
- **Clear** - Clear current playlist
- **+10 Songs** - Add 10 random songs
- **+5 Albums** - Add 5 random albums

## Player Synchronization (Multi-Room Audio)

### How Synchronization Works

Lyrion Music Server's synchronization creates perfect multi-room audio with <1ms accuracy:

1. **Select a player** on your remote (e.g., "Living Room")
2. **Open Remote Control** entity for that player
3. **Navigate to "Group Players" page**
4. **Tap another player** (e.g., "→ Kitchen") to sync
5. **Both players now play in perfect sync**
6. **Tap UNGROUP** to unsync the player

### Sync Group Behavior

- **Master Player**: First player in group controls playback
- **Volume**: Individual volume control maintained per player
- **Metadata**: All players show same track information
- **Adding Players**: Sync additional players to existing group
- **Removing Players**: Unsync removes player, group continues

### Example Multi-Room Setup

**Scenario**: Party mode - all players synchronized

1. Start music on "Living Room" player
2. Open "Kitchen" remote control → Group → "→ Living Room"
3. Open "Bedroom" remote control → Group → "→ Living Room"
4. Open "Garage" remote control → Group → "→ Living Room"
5. **Result**: All 4 players playing in perfect sync
6. **To stop**: Open any player remote → Group → "UNGROUP"

## Favorites Configuration

### Setting Up Favorites in LMS

1. **Open LMS Web Interface** (`http://YOUR_LMS_SERVER_IP:9000`)
2. **Navigate to**: Internet Radio, My Music, or Playlists
3. **Find content** you want as favorite
4. **Click the ❤️ icon** or use "Add to Favorites" option
5. **Restart integration** or re-run setup to reload favorites

### Favorites Limitations

- **Maximum 24 favorites** displayed on remote (LMS limitation on screen size)
- **All favorites** from LMS are loaded, top 24 shown
- **Nested folders** supported - subfolders treated as individual favorites
- **Any content type**: Radio, playlists, tracks, albums, artists


## Credits

- **Developer**: Meir Miyara
- **Lyrion Music Server**: Community-maintained open-source project (formerly Logitech Media Server)
- **Unfolded Circle**: Remote 2/3 integration framework (ucapi)
- **Squeezebox Community**: Decades of multi-room audio innovation
- **Community**: Testing and feedback from UC and LMS communities

## License

This project is licensed under the Mozilla Public License 2.0 (MPL-2.0) - see LICENSE file for details.

## Support & Community

- **GitHub Issues**: [Report bugs and request features](https://github.com/mase1981/uc-intg-lmserver/issues)
- **UC Community Forum**: [General discussion and support](https://unfolded.community/)
- **LMS Forums**: [Lyrion Music Server community](https://forums.lyrion.org/)
- **Developer**: [Meir Miyara](https://www.linkedin.com/in/meirmiyara)

---

**Made with ❤️ for the Unfolded Circle and Lyrion Music Server Communities**

**Thank You**: Meir Miyara
