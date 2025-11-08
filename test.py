#!/usr/bin/env python3
"""
Comprehensive TURN server test
Tests all possible TURN configurations to find working ones
"""

import asyncio
from aiortc import RTCPeerConnection, RTCConfiguration, RTCIceServer

# ExpressTurn credentials
USERNAME = "000000002076506456"
PASSWORD = "bK8A/K+WGDw/tYcuvM9/5xCnEZs="

# Test configurations
TEST_CONFIGS = [
    {
        "name": "ExpressTurn UDP 3478",
        "urls": ["turn:relay1.expressturn.com:3478"],
    },
    {
        "name": "ExpressTurn TCP 3478",
        "urls": ["turn:relay1.expressturn.com:3478?transport=tcp"],
    },
    {
        "name": "ExpressTurn TLS 5349",
        "urls": ["turns:relay1.expressturn.com:5349"],
    },
    {
        "name": "ExpressTurn TLS 5349 TCP",
        "urls": ["turns:relay1.expressturn.com:5349?transport=tcp"],
    },
    {
        "name": "ExpressTurn UDP 3480",
        "urls": ["turn:relay1.expressturn.com:3480"],
    },
    {
        "name": "ExpressTurn TCP 3480",
        "urls": ["turn:relay1.expressturn.com:3480?transport=tcp"],
    },
    {
        "name": "Twilio TURN UDP 3478",
        "urls": ["turn:global.turn.twilio.com:3478?transport=udp"],
        "username": "f4b4035eaa76f4a55de5f4351567653ee4ff6fa97b50b6b334fcc1be9c27212d",
        "password": "w1uxM55V9yVoqyVFjt+mxDBV0F87AUCemaYVQGxsPLw=",
    },
    {
        "name": "Twilio TURN TCP 3478",
        "urls": ["turn:global.turn.twilio.com:3478?transport=tcp"],
        "username": "f4b4035eaa76f4a55de5f4351567653ee4ff6fa97b50b6b334fcc1be9c27212d",
        "password": "w1uxM55V9yVoqyVFjt+mxDBV0F87AUCemaYVQGxsPLw=",
    },
    {
        "name": "Twilio TURN TCP 443",
        "urls": ["turn:global.turn.twilio.com:443?transport=tcp"],
        "username": "f4b4035eaa76f4a55de5f4351567653ee4ff6fa97b50b6b334fcc1be9c27212d",
        "password": "w1uxM55V9yVoqyVFjt+mxDBV0F87AUCemaYVQGxsPLw=",
    },
    {
        "name": "OpenRelay UDP 80",
        "urls": ["turn:openrelay.metered.ca:80"],
        "username": "openrelayproject",
        "password": "openrelayproject",
    },
    {
        "name": "OpenRelay TCP 80",
        "urls": ["turn:openrelay.metered.ca:80?transport=tcp"],
        "username": "openrelayproject",
        "password": "openrelayproject",
    },
    {
        "name": "OpenRelay TCP 443",
        "urls": ["turn:openrelay.metered.ca:443?transport=tcp"],
        "username": "openrelayproject",
        "password": "openrelayproject",
    },
]

async def test_turn_config(config):
    """Test a single TURN configuration"""
    print(f"\n{'='*60}")
    print(f"Testing: {config['name']}")
    print(f"URL: {config['urls'][0]}")
    print(f"{'='*60}")
    
    relay_found = False
    error_msg = None
    
    try:
        # Create peer connection with this TURN server + STUN
        ice_servers = [
            RTCIceServer(urls=["stun:stun.l.google.com:19302"]),
            RTCIceServer(
                urls=config["urls"],
                username=config.get("username", USERNAME),
                credential=config.get("password", PASSWORD),
            )
        ]
        
        pc = RTCPeerConnection(
            configuration=RTCConfiguration(iceServers=ice_servers)
        )
        
        # Track candidates
        candidates = []
        
        @pc.on("icecandidate")
        async def on_candidate(candidate):
            nonlocal relay_found
            if candidate:
                candidates.append(candidate.candidate)
                if "typ relay" in candidate.candidate:
                    relay_found = True
                    print(f"✅ RELAY candidate found!")
                    print(f"   {candidate.candidate[:100]}...")
        
        # Create offer to trigger ICE gathering
        print("⏳ Creating offer and gathering ICE candidates...")
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        
        # Wait for ICE gathering to complete (max 10 seconds)
        for i in range(100):
            if pc.iceGatheringState == "complete":
                break
            await asyncio.sleep(0.1)
        
        print(f"📊 ICE Gathering State: {pc.iceGatheringState}")
        print(f"📊 Total candidates: {len(candidates)}")
        
        # Analyze candidates
        host_count = sum(1 for c in candidates if "typ host" in c)
        srflx_count = sum(1 for c in candidates if "typ srflx" in c)
        relay_count = sum(1 for c in candidates if "typ relay" in c)
        
        print(f"   - HOST: {host_count}")
        print(f"   - SRFLX: {srflx_count}")
        print(f"   - RELAY: {relay_count}")
        
        await pc.close()
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error: {error_msg}")
    
    # Result
    if relay_found:
        print(f"✅ {config['name']}: WORKING!")
        return True
    else:
        print(f"❌ {config['name']}: NOT WORKING (no RELAY candidates)")
        return False

async def main():
    print("\n" + "="*60)
    print("🧪 COMPREHENSIVE TURN SERVER TEST")
    print("="*60)
    print("\nThis will test multiple TURN servers to find working ones.")
    print("Please wait, each test takes ~10 seconds...\n")
    
    working_configs = []
    
    for config in TEST_CONFIGS:
        try:
            result = await test_turn_config(config)
            if result:
                working_configs.append(config)
            await asyncio.sleep(1)  # Brief pause between tests
        except KeyboardInterrupt:
            print("\n\n⚠️ Test interrupted by user")
            break
    
    # Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    
    if working_configs:
        print(f"\n✅ {len(working_configs)} working configuration(s) found:\n")
        for config in working_configs:
            print(f"✓ {config['name']}")
            print(f"  URL: {config['urls'][0]}")
            print(f"  Username: {config.get('username', USERNAME)[:20]}...")
            print()
        
        print("\n💡 RECOMMENDED CONFIG FOR YOUR CODE:\n")
        best = working_configs[0]
        print("Python (Jetson):")
        print(f'RTCIceServer(')
        print(f'    urls={best["urls"]},')
        print(f'    username="{best.get("username", USERNAME)}",')
        print(f'    credential="{best.get("password", PASSWORD)}",')
        print(f')')
        
        print("\nTypeScript (Mobile):")
        print(f'{{')
        print(f'  urls: {best["urls"]},')
        print(f'  username: "{best.get("username", USERNAME)}",')
        print(f'  credential: "{best.get("password", PASSWORD)}",')
        print(f'}}')
    else:
        print("\n❌ NO WORKING TURN SERVERS FOUND!")
        print("\n💡 Possible reasons:")
        print("   1. All TURN servers are down/expired")
        print("   2. Firewall blocking all TURN traffic")
        print("   3. Network doesn't allow TURN protocols")
        print("\n💡 Solutions:")
        print("   1. Setup your own TURN server (Coturn)")
        print("   2. Use paid TURN service (Twilio, Xirsys)")
        print("   3. Test on same WiFi network (doesn't need TURN)")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Test stopped by user")