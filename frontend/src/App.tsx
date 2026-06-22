import { RouterProvider } from "react-router/dom";
import { QueryProvider } from "@/app/providers/QueryProvider";
import { SettingsProvider } from "@/app/providers/SettingsProvider";
import { router } from "@/app/router";

export default function App() {
  return (
    <QueryProvider>
      <SettingsProvider>
        <RouterProvider router={router} />
      </SettingsProvider>
    </QueryProvider>
  );
}
