// Railway Debug Helper
document.addEventListener("DOMContentLoaded", function () {
  console.log("Railway Debug Helper loaded");

  // Create debug container if it doesn't exist
  function createDebugContainer() {
    if (document.getElementById("railway-debug-container")) {
      return;
    }

    const container = document.createElement("div");
    container.id = "railway-debug-container";
    container.className = "mt-5 p-3 border rounded bg-light";
    container.innerHTML = `
      <h4>Railway Debug Information</h4>
      <div class="d-flex justify-content-between mb-3">
        <button id="railway-debug-fetch" class="btn btn-sm btn-primary">Fetch Debug Info</button>
        <button id="railway-debug-toggle" class="btn btn-sm btn-secondary">Show/Hide Details</button>
      </div>
      <div id="railway-debug-status" class="mb-2">Status: Not fetched</div>
      <div id="railway-debug-content" style="display: none; max-height: 400px; overflow-y: auto;">
        <pre id="railway-debug-json" class="p-2 bg-dark text-light rounded">No data</pre>
      </div>
    `;

    document.body.appendChild(container);

    // Add event listeners
    document.getElementById("railway-debug-fetch").addEventListener("click", fetchRailwayDebug);
    document.getElementById("railway-debug-toggle").addEventListener("click", toggleDebugContent);
  }

  // Toggle debug content visibility
  function toggleDebugContent() {
    const content = document.getElementById("railway-debug-content");
    if (content) {
      content.style.display = content.style.display === "none" ? "block" : "none";
    }
  }

  // Fetch Railway debug information
  async function fetchRailwayDebug() {
    const statusElement = document.getElementById("railway-debug-status");
    const jsonElement = document.getElementById("railway-debug-json");

    if (!statusElement || !jsonElement) {
      console.error("Debug elements not found");
      return;
    }

    statusElement.textContent = "Status: Fetching...";

    try {
      const baseUrl = window.location.origin;
      const debugUrl = `${baseUrl}/railway/debug`;
      console.log(`Fetching Railway debug info from ${debugUrl}`);

      const response = await fetch(debugUrl, {
        headers: {
          "Cache-Control": "no-cache",
          Pragma: "no-cache",
        },
        credentials: "include",
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      console.log("Railway debug info:", data);

      // Format and display the data
      jsonElement.textContent = JSON.stringify(data, null, 2);
      statusElement.textContent = `Status: Fetched at ${new Date().toLocaleTimeString()}`;

      // Show the content
      document.getElementById("railway-debug-content").style.display = "block";

      // Check for active debates
      if (data.active_debates && data.active_debates.length > 0) {
        statusElement.textContent += ` | Active debates: ${data.active_debates.length}`;
      }

      return data;
    } catch (error) {
      console.error("Error fetching Railway debug info:", error);
      statusElement.textContent = `Status: Error - ${error.message}`;
      jsonElement.textContent = `Error: ${error.message}`;
      return null;
    }
  }

  // Initialize debug container
  createDebugContainer();

  // Auto-fetch debug info on load
  setTimeout(fetchRailwayDebug, 1000);
});
