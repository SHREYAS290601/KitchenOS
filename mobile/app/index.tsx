import { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { Link } from "expo-router";

import { getHealth } from "../api/client";

const SECTIONS = ["Checklist", "Pantry", "Assist", "Settings"] as const;

type Reachability = "checking" | "reachable" | "unreachable";

export default function HomeScreen() {
  const [backend, setBackend] = useState<Reachability>("checking");

  useEffect(() => {
    let active = true;
    getHealth().then((result) => {
      if (active) setBackend(result.ok ? "reachable" : "unreachable");
    });
    return () => {
      active = false;
    };
  }, []);

  return (
    <View style={styles.container}>
      <Text accessibilityRole="header" style={styles.heading}>
        PantryOps Edge
      </Text>
      <Text accessibilityLiveRegion="polite" style={styles.status}>
        Backend: {backend}
      </Text>
      <View style={styles.sections}>
        <Link href="/assist" style={styles.assistLink} accessibilityRole="link">
          Open the working shopping assistant
        </Link>
        <Link href="/check-in" style={styles.assistLink} accessibilityRole="link">
          Check in groceries with photos
        </Link>
        {SECTIONS.map((section) => (
          <View key={section} style={styles.sectionStub}>
            <Text accessibilityRole="header" style={styles.sectionTitle}>
              {section}
            </Text>
            <Text style={styles.sectionBody}>Coming in a later phase.</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, gap: 12 },
  heading: { fontSize: 28, fontWeight: "700" },
  status: { fontSize: 16, color: "#374151" },
  sections: { gap: 8, marginTop: 8 },
  sectionStub: {
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#D1D5DB",
  },
  sectionTitle: { fontSize: 18, fontWeight: "600" },
  sectionBody: { fontSize: 14, color: "#4B5563" },
  assistLink: { padding: 14, borderRadius: 8, backgroundColor: "#0F766E", color: "white", fontWeight: "700", textAlign: "center" },
});
