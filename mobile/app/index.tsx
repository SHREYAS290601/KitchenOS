import { StyleSheet, Text, View } from "react-native";

const SECTIONS = ["Checklist", "Pantry", "Assist", "Check-in", "Settings"] as const;

export default function HomeScreen() {
  return (
    <View style={styles.container}>
      <Text accessibilityRole="header" style={styles.heading}>
        PantryOps Edge
      </Text>
      <Text style={styles.status}>Backend: status unknown</Text>
      <View style={styles.sections}>
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
});
