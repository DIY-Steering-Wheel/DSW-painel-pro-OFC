const WebSocket = require('ws');
const express = require('express');
const app = express();
const wsport = 2609;
const httpport = 2608;
const wsadress = "ws://localhost:" + wsport.toString();
const httpadress = "http://localhost:" + httpport.toString();
let isRun = false;


app.use(express.static('public'));

// Create a new WebSocket server on port
const wss = new WebSocket.Server({ port: wsport });

// Define a function to send telemetry data to all connected clients
function broadcastTelemetryData(data) {
  wss.clients.forEach((client) => {
    if (client.readyState === WebSocket.OPEN) {
      client.send(JSON.stringify(data));
    }
  });
}

// Define an event that will be triggered when a client connects
wss.on('connection', (ws) => {
  console.log('Client connected');

  // Define an event that will be triggered when the server receives telemetry data from the client
  ws.on('message', (data) => {
    if ( !isRun && data !== null){
      console.log("Recieving telemetry data from MSC...");
      isRun = true;
    }
    //console.log(`Received telemetry data from client: ${data}`);

    // Broadcast the telemetry data to all connected clients (including the sender)
    broadcastTelemetryData(JSON.parse(data));
  });

  // Define an event that will be triggered when a client disconnects
  ws.on('close', () => {
    console.log('Client disconnected');
  });
});

// Serve the client-side code
app.get('/', (req, res) => {
  res.sendFile(__dirname + '/public/index.html');
});

// Start the server
const server = app.listen(httpport, () => {
  console.log("------------------------------------------------------------------------------------------------")
  console.log('Welcome to the MSC Vehicle Telemetry Mod. Please use your web browser to connect to the website.');
  console.log("- connect to:");
  console.log(httpadress);
  console.log("------------------------------------------------------------------------------------------------")
});

// Create a WebSocket connection to the server
/*const socket = new WebSocket(wsadress);

socket.addEventListener('open', (event) => {
  console.log('WebSocket connection opened');
});

socket.addEventListener('message', (event) => {
  //console.log(`Received message from server: ${event.data}`);
});

socket.addEventListener('close', (event) => {
  console.log('WebSocket connection closed');
});*/
