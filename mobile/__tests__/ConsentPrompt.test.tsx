import { fireEvent, render, screen } from "@testing-library/react-native";

import { ConsentPrompt } from "../screens/ConsentPrompt";


it("offers three explicit accessible consent choices", async () => {
  const onConfirm = jest.fn();
  await render(<ConsentPrompt onConfirm={onConfirm} />);

  const session = screen.getByRole("radio", {
    name: "Yes, save for this shopping session",
  });
  expect(session.props.accessibilityState.checked).toBe(false);

  await fireEvent.press(session);
  expect(screen.getByRole("radio", {
    name: "Yes, save for this shopping session",
  }).props.accessibilityState.checked).toBe(true);
  await fireEvent.press(screen.getByRole("button", { name: "Confirm image consent" }));

  expect(onConfirm).toHaveBeenCalledWith("session");
  expect(screen.getByRole("radio", { name: "Always save grocery images" })).toBeTruthy();
  expect(screen.getByRole("radio", { name: "Do not save after answering" })).toBeTruthy();
});
