import { useState } from "react";

import { CaptureScreen } from "../camera/CaptureScreen";
import { AssistScreen } from "../screens/AssistScreen";

export default function AssistRoute() {
  const [capturing, setCapturing] = useState(false);
  const [photoUri, setPhotoUri] = useState<string | null>(null);
  if (capturing) {
    return <CaptureScreen onCancel={() => setCapturing(false)} onUsePhoto={(uri) => { setPhotoUri(uri); setCapturing(false); }} />;
  }
  return <AssistScreen onOpenCamera={() => setCapturing(true)} photoUri={photoUri} onRemovePhoto={() => setPhotoUri(null)} />;
}
