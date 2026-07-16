import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";

jest.mock("@react-native-async-storage/async-storage", () =>
  require("@react-native-async-storage/async-storage/jest/async-storage-mock"),
);

import { AssistScreen } from "../screens/AssistScreen";


it("submits an accessible question and announces the answer", async () => {
  let resolveAsk!: (value: any) => void;
  const ask = jest.fn().mockReturnValue(new Promise((resolve) => { resolveAsk = resolve; }));
  await render(<AssistScreen ask={ask} onOpenCamera={jest.fn()} />);

  await fireEvent.changeText(screen.getByLabelText("Shopping question"), "Should I buy this yogurt?");
  await fireEvent.press(screen.getByRole("button", { name: "Ask shopping assistant" }));

  expect(screen.getByText("Answer pending")).toBeTruthy();
  resolveAsk({
    ok: true,
    data: {
      answer: "Compare the label with your saved preferences.",
      applied_preference_ids: [],
      audit: { verdict: "pass", reasons: [] },
      degraded: false,
    },
  });
  await waitFor(() => expect(screen.getByText("Compare the label with your saved preferences.")).toBeTruthy());
  expect(screen.getByTestId("assist-answer").props.accessibilityLiveRegion).toBe("polite");
});


it("shows an attached photo with a labeled remove control", async () => {
  const onRemovePhoto = jest.fn();
  await render(
    <AssistScreen
      ask={jest.fn()}
      onOpenCamera={jest.fn()}
      photoUri="file:///photo.jpg"
      onRemovePhoto={onRemovePhoto}
    />,
  );
  expect(screen.getByLabelText("Attached grocery product photo")).toBeTruthy();
  await fireEvent.press(screen.getByRole("button", { name: "Remove attached photo" }));
  expect(onRemovePhoto).toHaveBeenCalled();
});
