import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it } from "vitest";
import { DashboardShell } from "@/components/dashboard-shell";

describe("DashboardShell", () => {
  it("renders a company research search", () => {
    render(<DashboardShell />);
    expect(screen.getByLabelText("Company research query")).toBeInTheDocument();
  });
});
