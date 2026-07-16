import React from "react";
import { fireEvent, render, screen } from "@testing-library/react-native";

import { EstimatedField } from "../components/EstimatedField";

const brandField = {
  value: "Chobani",
  source: "label_ocr",
  confidence: 0.84,
  status: "estimated" as const,
};

describe("EstimatedField", () => {
  it("renders value, source, and confidence as text", async () => {
    await render(
      <EstimatedField fieldName="brand" field={brandField} onAction={jest.fn()} />,
    );
    expect(screen.getByText("Brand: Chobani — Label OCR, 84%")).toBeTruthy();
    expect(screen.getByText(/Estimated/)).toBeTruthy();
  });

  it("exposes the four actions as buttons with field-naming labels", async () => {
    await render(
      <EstimatedField fieldName="brand" field={brandField} onAction={jest.fn()} />,
    );
    expect(screen.getByRole("button", { name: "Confirm brand Chobani" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Edit brand" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Reject brand Chobani" })).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "Leave brand as estimate" }),
    ).toBeTruthy();
  });

  it("fires onAction with the chosen action", async () => {
    const onAction = jest.fn();
    await render(
      <EstimatedField fieldName="brand" field={brandField} onAction={onAction} />,
    );
    await fireEvent.press(screen.getByRole("button", { name: "Confirm brand Chobani" }));
    expect(onAction).toHaveBeenCalledWith("confirm");
    await fireEvent.press(screen.getByRole("button", { name: "Leave brand as estimate" }));
    expect(onAction).toHaveBeenCalledWith("leave_as_estimate");
  });

  it("conveys user_confirmed status as text, not color", async () => {
    await render(
      <EstimatedField
        fieldName="brand"
        field={{ ...brandField, source: "user_confirmed", status: "user_confirmed" }}
        onAction={jest.fn()}
      />,
    );
    expect(screen.getByText(/Confirmed by you/)).toBeTruthy();
  });
});
