/**
 * WebRTC Configuration with Metered TURN Servers
 * Using Metered.ca paid service for reliable TURN servers
 * API Key: 6cc0b031d2951fbd7ac079906c6b0470b02a
 */

// Metered ICE Servers Configuration
const iceServers = [
  {
    urls: "stun:stun.relay.metered.ca:80",
  },
  {
    urls: "turn:standard.relay.metered.ca:80",
    username: "93e17668232018bed69fae39",
    credential: "/NDIlk/I1eVxIjo2",
  },
  {
    urls: "turn:standard.relay.metered.ca:80?transport=tcp",
    username: "93e17668232018bed69fae39",
    credential: "/NDIlk/I1eVxIjo2",
  },
  {
    urls: "turn:standard.relay.metered.ca:443",
    username: "93e17668232018bed69fae39",
    credential: "/NDIlk/I1eVxIjo2",
  },
  {
    urls: "turns:standard.relay.metered.ca:443?transport=tcp",
    username: "93e17668232018bed69fae39",
    credential: "/NDIlk/I1eVxIjo2",
  },
];

// Create RTCPeerConnection with OpenRelay TURN servers
const myPeerConnection = new RTCPeerConnection({
  iceServers: iceServers,
  // Optional: Configure ICE transport policy
  // iceTransportPolicy: 'all', // or 'relay' to force TURN
});

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { iceServers, myPeerConnection };
}

/**
 * USAGE NOTES:
 * 
 * 1. Metered.ca provides reliable TURN servers with SLA
 * 2. API Key: 6cc0b031d2951fbd7ac079906c6b0470b02a
 * 3. Credentials are rotated periodically for security
 * 
 * 4. Available protocols:
 *    - STUN on port 80
 *    - TURN UDP on port 80
 *    - TURN TCP on port 80
 *    - TURN UDP on port 443
 *    - TURN TLS on port 443
 * 
 * 5. For React Native or mobile apps, use the same configuration:
 */

// Example for React Native
const reactNativeConfig = {
  iceServers: [
    {
      urls: 'stun:stun.relay.metered.ca:80',
    },
    {
      urls: 'turn:standard.relay.metered.ca:80',
      username: '93e17668232018bed69fae39',
      credential: '/NDIlk/I1eVxIjo2',
    },
    {
      urls: 'turn:standard.relay.metered.ca:80?transport=tcp',
      username: '93e17668232018bed69fae39',
      credential: '/NDIlk/I1eVxIjo2',
    },
    {
      urls: 'turn:standard.relay.metered.ca:443',
      username: '93e17668232018bed69fae39',
      credential: '/NDIlk/I1eVxIjo2',
    },
    {
      urls: 'turns:standard.relay.metered.ca:443?transport=tcp',
      username: '93e17668232018bed69fae39',
      credential: '/NDIlk/I1eVxIjo2',
    },
  ],
};

// Example: Force TURN (relay) only
const forceTurnConfig = {
  iceServers: [
    {
      urls: 'turn:standard.relay.metered.ca:80',
      username: '93e17668232018bed69fae39',
      credential: '/NDIlk/I1eVxIjo2',
    },
    {
      urls: 'turn:standard.relay.metered.ca:443',
      username: '93e17668232018bed69fae39',
      credential: '/NDIlk/I1eVxIjo2',
    },
  ],
  iceTransportPolicy: 'relay', // This forces using TURN only
};

console.log('✅ Metered TURN configuration loaded');
console.log('📡 Available ICE servers:', iceServers.length);
