import { act, fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import { ImageManipulator } from "expo-image-manipulator";
import * as ImagePicker from "expo-image-picker";

import { CheckInScreen, pickGroceryPhotos } from "../screens/CheckInScreen";

const makeProps = () => ({
  shoppingSessionId: "client-session",
  pickPhotos: jest.fn().mockResolvedValue(["file:///groceries-1.jpg"]),
  grantConsent: jest.fn().mockResolvedValue({ ok: true as const, sessionId: "server-session" }),
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
  expect(props.grantConsent).toHaveBeenCalledWith("session", "client-session");
  expect(props.uploadPhoto).toHaveBeenCalledWith("file:///groceries-1.jpg", "server-session");
  expect(props.postCheckIn).toHaveBeenCalledWith(
    ["11111111-1111-1111-1111-111111111111"],
    "server-session",
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


it("retries polling after a transient status failure", async () => {
  jest.useFakeTimers();
  const props = makeProps();
  props.getJobStatus
    .mockResolvedValueOnce({ ok: false, message: "Temporarily offline" })
    .mockResolvedValueOnce({
      ok: true,
      data: { jobId: "22222222-2222-2222-2222-222222222222", status: "completed", steps: [] },
    });
  await render(<CheckInScreen {...props} />);
  await fireEvent.press(screen.getByRole("button", { name: "Add grocery photos" }));
  await fireEvent.press(screen.getByRole("button", { name: "Start grocery check-in" }));
  await waitFor(() => expect(screen.getByText("Temporarily offline")).toBeTruthy());

  await act(async () => { jest.advanceTimersByTime(1000); });

  await waitFor(() => expect(screen.getByText("Overall status: completed")).toBeTruthy());
  expect(props.getJobStatus).toHaveBeenCalledTimes(2);
  jest.useRealTimers();
});


it("prevents duplicate submission after a job is accepted", async () => {
  const props = makeProps();
  props.getJobStatus.mockReturnValue(new Promise(() => {}));
  await render(<CheckInScreen {...props} />);
  await fireEvent.press(screen.getByRole("button", { name: "Add grocery photos" }));
  const submit = screen.getByRole("button", { name: "Start grocery check-in" });
  await fireEvent.press(submit);
  await waitFor(() => expect(props.postCheckIn).toHaveBeenCalledTimes(1));

  await fireEvent.press(submit);

  expect(props.postCheckIn).toHaveBeenCalledTimes(1);
  expect(submit.props.accessibilityState.disabled).toBe(true);
});


it("lets the user remove a selected photo and shows visible focus", async () => {
  const props = makeProps();
  await render(<CheckInScreen {...props} />);
  const picker = screen.getByRole("button", { name: "Add grocery photos" });
  await fireEvent(picker, "focus");
  expect(screen.getByTestId("add-photos")).toHaveStyle({ borderColor: "#0F172A", borderWidth: 3 });
  await fireEvent.press(picker);
  const remove = await screen.findByRole("button", { name: "Remove selected grocery photo 1" });
  await fireEvent(remove, "focus");
  expect(remove).toHaveStyle({ borderColor: "#0F172A", borderWidth: 3 });
  await fireEvent(remove, "blur");
  await fireEvent.press(remove);
  expect(screen.getByText("0 photos selected")).toBeTruthy();
});


it("disables the image picker microphone permission", () => {
  const config = require("../app.json");
  const plugin = config.expo.plugins.find((entry: unknown) => Array.isArray(entry) && entry[0] === "expo-image-picker");
  expect(plugin[1].microphonePermission).toBe(false);
});


it("normalizes selected images to bounded JPEG files", async () => {
  jest.spyOn(ImagePicker, "launchImageLibraryAsync").mockResolvedValue({
    canceled: false,
    assets: [{ uri: "file:///large.png", width: 5000, height: 2500 }],
  } as ImagePicker.ImagePickerResult);
  const saveAsync = jest.fn().mockResolvedValue({ uri: "file:///normalized.jpg" });
  const releaseRendered = jest.fn();
  const renderAsync = jest.fn().mockResolvedValue({ saveAsync, release: releaseRendered });
  const resize = jest.fn();
  const releaseContext = jest.fn();
  jest.spyOn(ImageManipulator, "manipulate").mockReturnValue({
    resize,
    renderAsync,
    release: releaseContext,
  } as never);

  const result = await pickGroceryPhotos();

  expect(result).toEqual(["file:///normalized.jpg"]);
  expect(ImagePicker.launchImageLibraryAsync).toHaveBeenCalledWith(expect.objectContaining({
    allowsMultipleSelection: true,
    selectionLimit: 20,
  }));
  expect(resize).toHaveBeenCalledWith({ width: 4096, height: 2048 });
  expect(saveAsync).toHaveBeenCalledWith(expect.objectContaining({ format: "jpeg" }));
  expect(releaseRendered).toHaveBeenCalledTimes(1);
  expect(releaseContext).toHaveBeenCalledTimes(1);
  jest.restoreAllMocks();
});


it("returns no images when selection is canceled", async () => {
  jest.spyOn(ImagePicker, "launchImageLibraryAsync").mockResolvedValue({
    canceled: true,
    assets: null,
  });

  await expect(pickGroceryPhotos()).resolves.toEqual([]);
  jest.restoreAllMocks();
});


it("keeps already bounded images at their original dimensions", async () => {
  jest.spyOn(ImagePicker, "launchImageLibraryAsync").mockResolvedValue({
    canceled: false,
    assets: [{ uri: "file:///small.jpg", width: 1200, height: 800 }],
  } as ImagePicker.ImagePickerResult);
  const saveAsync = jest.fn().mockResolvedValue({ uri: "file:///small-normalized.jpg" });
  const resize = jest.fn();
  jest.spyOn(ImageManipulator, "manipulate").mockReturnValue({
    resize,
    renderAsync: jest.fn().mockResolvedValue({ saveAsync, release: jest.fn() }),
    release: jest.fn(),
  } as never);

  await expect(pickGroceryPhotos()).resolves.toEqual(["file:///small-normalized.jpg"]);
  expect(resize).not.toHaveBeenCalled();
  jest.restoreAllMocks();
});


it("shows a picker error without changing the selection", async () => {
  const props = makeProps();
  props.pickPhotos.mockRejectedValue(new Error("picker unavailable"));
  await render(<CheckInScreen {...props} />);

  await fireEvent.press(screen.getByRole("button", { name: "Add grocery photos" }));

  expect(await screen.findByText("Grocery photos could not be selected")).toBeTruthy();
  expect(screen.getByText("0 photos selected")).toBeTruthy();
});


it("stops before uploading when consent is rejected", async () => {
  const props = makeProps();
  props.grantConsent.mockResolvedValue({ ok: false, message: "Consent is required" });
  await render(<CheckInScreen {...props} />);
  await fireEvent.press(screen.getByRole("button", { name: "Add grocery photos" }));

  await fireEvent.press(screen.getByRole("button", { name: "Start grocery check-in" }));

  expect(await screen.findByText("Consent is required")).toBeTruthy();
  expect(props.uploadPhoto).not.toHaveBeenCalled();
  expect(screen.getByRole("button", { name: "Start grocery check-in" }).props.accessibilityState.disabled).toBe(false);
});


it("stops sequential uploads on the first failed image", async () => {
  const props = makeProps();
  props.pickPhotos.mockResolvedValue(["file:///one.jpg", "file:///two.jpg"]);
  props.uploadPhoto.mockResolvedValueOnce({ ok: false, message: "Upload rejected" });
  await render(<CheckInScreen {...props} />);
  await fireEvent.press(screen.getByRole("button", { name: "Add grocery photos" }));

  await fireEvent.press(screen.getByRole("button", { name: "Start grocery check-in" }));

  expect(await screen.findByText("Upload rejected")).toBeTruthy();
  expect(props.uploadPhoto).toHaveBeenCalledTimes(1);
  expect(props.postCheckIn).not.toHaveBeenCalled();
});


it("shows check-in creation failures and allows a retry", async () => {
  const props = makeProps();
  props.postCheckIn.mockResolvedValue({ ok: false, message: "Check-in could not start" });
  await render(<CheckInScreen {...props} />);
  await fireEvent.press(screen.getByRole("button", { name: "Add grocery photos" }));

  await fireEvent.press(screen.getByRole("button", { name: "Start grocery check-in" }));

  expect(await screen.findByText("Check-in could not start")).toBeTruthy();
  expect(screen.getByRole("button", { name: "Start grocery check-in" }).props.accessibilityState.disabled).toBe(false);
});


it("uses safe copy when a background job fails", async () => {
  const props = makeProps();
  props.getJobStatus.mockResolvedValue({
    ok: true,
    data: { jobId: "22222222-2222-2222-2222-222222222222", status: "failed", steps: [] },
  });
  await render(<CheckInScreen {...props} />);
  await fireEvent.press(screen.getByRole("button", { name: "Add grocery photos" }));
  await fireEvent.press(screen.getByRole("button", { name: "Start grocery check-in" }));

  expect(await screen.findByText("Processing stopped. Please start a new check-in.")).toBeTruthy();
});


it("locks photo selection while consent and upload are in flight", async () => {
  let resolveConsent!: (value: { ok: false; message: string }) => void;
  const props = makeProps();
  props.grantConsent.mockReturnValue(new Promise((resolve) => { resolveConsent = resolve; }));
  await render(<CheckInScreen {...props} />);
  await fireEvent.press(screen.getByRole("button", { name: "Add grocery photos" }));

  await fireEvent.press(screen.getByRole("button", { name: "Start grocery check-in" }));

  expect(screen.getByRole("button", { name: "Add grocery photos" }).props.accessibilityState.disabled).toBe(true);
  expect(screen.getByRole("button", { name: "Remove selected grocery photo 1" }).props.accessibilityState.disabled).toBe(true);
  resolveConsent({ ok: false, message: "Consent canceled" });
  expect(await screen.findByText("Consent canceled")).toBeTruthy();
});
