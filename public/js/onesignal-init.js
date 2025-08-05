<!-- OneSignal SDK -->
<script src="https://cdn.onesignal.com/sdks/OneSignalSDK.js" async></script>
<script>
  window.OneSignal = window.OneSignal || [];
  OneSignal.push(function() {
    OneSignal.init({
      appId: "ONESIGNAL_APP_ID", // <-- Reemplaza con tu ID real
      safari_web_id: "",
      notifyButton: {
        enable: true
      }
    });
  });
</script>
