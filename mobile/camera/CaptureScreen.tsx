import { CameraView, useCameraPermissions } from "expo-camera";
import { useRef, useState } from "react";
import { Image, Pressable, StyleSheet, Text, View } from "react-native";

export function CaptureScreen({ onUsePhoto, onCancel }: { onUsePhoto: (uri: string) => void; onCancel: () => void }) {
  const camera = useRef<CameraView>(null);
  const [permission, requestPermission] = useCameraPermissions();
  const [ready, setReady] = useState(false);
  const [photoUri, setPhotoUri] = useState<string | null>(null);

  if (!permission) return <View><Text>Checking camera permission</Text></View>;
  if (!permission.granted) {
    return <View style={styles.message}>
      <Text>Camera access is needed only when you choose to attach a grocery photo.</Text>
      <Pressable accessibilityRole="button" accessibilityLabel="Grant camera permission" onPress={() => void requestPermission()} style={styles.button}><Text style={styles.buttonText}>Grant camera permission</Text></Pressable>
      <Pressable accessibilityRole="button" accessibilityLabel="Cancel photo capture" onPress={onCancel} style={styles.secondary}><Text>Cancel</Text></Pressable>
    </View>;
  }
  if (photoUri) {
    return <View style={styles.preview}>
      <Image source={{ uri: photoUri }} accessibilityLabel="Photo preview" style={styles.photo} />
      <Pressable accessibilityRole="button" accessibilityLabel="Use this grocery photo" onPress={() => onUsePhoto(photoUri)} style={styles.button}><Text style={styles.buttonText}>Use photo</Text></Pressable>
      <Pressable accessibilityRole="button" accessibilityLabel="Retake grocery photo" onPress={() => setPhotoUri(null)} style={styles.secondary}><Text>Retake</Text></Pressable>
    </View>;
  }
  const capture = async () => {
    if (!ready) return;
    const photo = await camera.current?.takePictureAsync({ quality: 0.75 });
    if (photo?.uri) setPhotoUri(photo.uri);
  };
  return <View style={styles.container}>
    <CameraView ref={camera} style={styles.camera} facing="back" onCameraReady={() => setReady(true)} />
    <Pressable accessibilityRole="button" accessibilityLabel="Take grocery product photo" accessibilityState={{ disabled: !ready }} disabled={!ready} onPress={() => void capture()} style={styles.shutter}><Text style={styles.buttonText}>{ready ? "Take photo" : "Camera loading"}</Text></Pressable>
    <Pressable accessibilityRole="button" accessibilityLabel="Cancel photo capture" onPress={onCancel} style={styles.secondary}><Text>Cancel</Text></Pressable>
  </View>;
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#020617", paddingBottom: 24, gap: 12 },
  camera: { flex: 1 },
  message: { flex: 1, justifyContent: "center", padding: 24, gap: 16 },
  preview: { flex: 1, padding: 18, gap: 12, backgroundColor: "#F8FAFC" },
  photo: { flex: 1, borderRadius: 12 },
  button: { backgroundColor: "#0F766E", borderRadius: 8, padding: 14, alignItems: "center" },
  shutter: { marginHorizontal: 18, backgroundColor: "#0F766E", borderRadius: 30, padding: 16, alignItems: "center" },
  buttonText: { color: "white", fontWeight: "700" },
  secondary: { marginHorizontal: 18, backgroundColor: "white", borderRadius: 8, padding: 12, alignItems: "center" },
});
