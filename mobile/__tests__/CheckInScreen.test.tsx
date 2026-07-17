import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";

import { CheckInScreen } from "../screens/CheckInScreen";

const makeProps = () => ({
  pickPhotos: jest.fn().mockResolvedValue(["file:///groceries-1.jpg"]),
  grantConsent: jest.fn().mockResolvedValue({ ok: true as const }),
  uploadPhoto: jest.fn().mockResolvedValue({ ok: true as const, imageId: "11111111-1111-1111-1111-111111111111" }),
  postCheckIn: jest.fn().mockResolvedValue({ ok: true as const, data: { jobId: "22222222-2222-2222-2222-222222222222", status: "queued", steps: [] } }),
  getJobStatus: jest.fn().mockResolvedValue({ ok: true as const, data: { jobId: "22222222-2222-2222-2222-222222222222", status: "completed", steps: [] } }),
});


it("renders an accessible multi-photo picker", async () => {
  const props = makeProps();
  await render(<CheckInScreen {...props} />);

  await fireEvent.press(screen.getByRole("button", { name: "Add grocery photos" }));

  expect(props.pickPhotos).toHaveBeenCalledTimes(1);
  expect(await screen.findByText("1 photo selected")).toBeTruthy();
});


it("blocks zero-photo submission with a field-specific error", async () => {
  const props = makeProps();
  await render(<CheckInScreen {...props} />);

  await fireEvent.press(screen.getByRole("button", { name: "Start grocery check-in" }));

  expect(screen.getByText("Grocery photos are required")).toBeTruthy();
  expect(props.postCheckIn).not.toHaveBeenCalled();
});


it("submits photos and announces background processing", async () => {
  const props = makeProps();
  await render(<CheckInScreen {...props} />);
  await fireEvent.press(screen.getByRole("button", { name: "Add grocery photos" }));

  await fireEvent.press(screen.getByRole("button", { name: "Start grocery check-in" }));

  await waitFor(() => {
    expect(screen.getByText("Processing in background — you can keep using the app")).toBeTruthy();
  });
  expect(props.grantConsent).toHaveBeenCalledWith("session", "mobile-session");
  expect(props.uploadPhoto).toHaveBeenCalledWith("file:///groceries-1.jpg", "mobile-session");
  expect(props.postCheckIn).toHaveBeenCalledWith(
    ["11111111-1111-1111-1111-111111111111"],
    "mobile-session",
  );
  expect(screen.getByTestId("check-in-status").props.accessibilityLiveRegion).toBe("polite");
});


it("renders every polled step with a textual status", async () => {
  const props = makeProps();
  props.getJobStatus.mockResolvedValue({
    ok: true,
    data: {
      jobId: "22222222-2222-2222-2222-222222222222",
      status: "processing",
      steps: [
        { step: "image_storage", status: "completed" },
        { step: "segmentation", status: "processing" },
      ],
    },
  });
  await render(<CheckInScreen {...props} />);
  await fireEvent.press(screen.getByRole("button", { name: "Add grocery photos" }));
  await fireEvent.press(screen.getByRole("button", { name: "Start grocery check-in" }));

  expect(await screen.findByText("image storage: completed")).toBeTruthy();
  expect(screen.getByText("segmentation: processing")).toBeTruthy();
});
