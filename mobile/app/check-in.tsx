import { useLocalSearchParams } from "expo-router";

import { CheckInScreen } from "../screens/CheckInScreen";

function firstParam(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default function CheckInRoute() {
  const { shoppingListLabel } = useLocalSearchParams<{
    shoppingListLabel?: string | string[];
  }>();

  return <CheckInScreen shoppingListLabel={firstParam(shoppingListLabel)} />;
}
