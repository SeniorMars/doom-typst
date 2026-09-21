// Tinymist preview transport probe. Requires Node with built-in WebSocket.
// Measures receipt of rendered document packets, not browser paint completion.
import { createHash } from 'node:crypto';
const socket = new WebSocket(process.argv[2]);
socket.binaryType = 'arraybuffer';
let initialRequest;
socket.onopen = () => {
  socket.send('current');
  initialRequest = setInterval(() => socket.send('current'), 100);
};
socket.onmessage = ({ data }) => {
  if (typeof data === 'string') return;
  const buffer = Buffer.from(data);
  const prefix = buffer.subarray(0, 8).toString();
  if (!prefix.startsWith('new,') && !prefix.startsWith('diff,') && !prefix.startsWith('diff-v1,')) return;
  clearInterval(initialRequest);
  console.log(JSON.stringify({
    bytes: buffer.length,
    packet_sha256: createHash('sha256').update(buffer).digest('hex'),
  }));
};
socket.onerror = () => { console.error('Preview websocket failed'); process.exit(1); };
socket.onclose = () => { clearInterval(initialRequest); process.exit(0); };
