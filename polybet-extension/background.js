// Open the side panel when the user clicks the extension icon in the toolbar.
chrome.sidePanel
  .setPanelBehavior({ openPanelOnAction: true })
  .catch((error) => console.error(error));
