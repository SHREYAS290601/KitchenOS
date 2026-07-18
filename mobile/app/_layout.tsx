import { Stack } from "expo-router";

export default function RootLayout() {
  return (
    <Stack
      screenOptions={{
        headerTitleStyle: { fontWeight: "600" },
      }}
    >
      <Stack.Screen name="index" options={{ title: "PantryOps Edge" }} />
      <Stack.Screen name="assist" options={{ title: "Shopping Assistant" }} />
      <Stack.Screen name="shopping" options={{ title: "Shopping Checklist" }} />
      <Stack.Screen name="check-in" options={{ title: "Grocery Check-In" }} />
      <Stack.Screen name="settings" options={{ title: "Connection Security" }} />
    </Stack>
  );
}
