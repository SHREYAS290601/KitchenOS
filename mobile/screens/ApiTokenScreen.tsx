import { useState } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { saveApiToken } from "../api/client";

type Props = {
  saveToken?: (token: string) => Promise<void>;
};

export function ApiTokenScreen({ saveToken = saveApiToken }: Props) {
  const [token, setToken] = useState("");
  const [status, setStatus] = useState("");
  const [saving, setSaving] = useState(false);
  const valid = token.trim().length >= 32;

  const save = async () => {
    if (!valid || saving) return;
    setSaving(true);
    setStatus("");
    try {
      await saveToken(token);
      setToken("");
      setStatus("API credential saved securely on this device");
    } catch {
      setStatus("API credential could not be saved");
    } finally {
      setSaving(false);
    }
  };

  return (
    <View style={styles.container}>
      <Text accessibilityRole="header" style={styles.heading}>Connect this device</Text>
      <Text>Enter the personal API credential from your PantryOps server. It is stored in encrypted device storage.</Text>
      <TextInput
        accessibilityLabel="PantryOps API credential"
        autoCapitalize="none"
        autoCorrect={false}
        secureTextEntry
        value={token}
        onChangeText={setToken}
        style={styles.input}
      />
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Save API credential"
        accessibilityState={{ disabled: !valid || saving }}
        disabled={!valid || saving}
        onPress={() => void save()}
        style={styles.button}
      >
        <Text style={styles.buttonText}>{saving ? "Saving…" : "Save credential"}</Text>
      </Pressable>
      <Text accessibilityLiveRegion="polite">{status}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 18, gap: 14, backgroundColor: "#F8FAFC" },
  heading: { fontSize: 28, fontWeight: "800", color: "#0F172A" },
  input: { padding: 14, borderWidth: 2, borderColor: "#64748B", borderRadius: 8, backgroundColor: "white" },
  button: { padding: 14, borderRadius: 9, alignItems: "center", backgroundColor: "#0F766E" },
  buttonText: { color: "white", fontWeight: "700" },
});
