---
version: "1.0.0"
name: "Industrial Operations System"
description: "Visual language for industrial software focusing on mismatch detection and operational clarity."
colors:
  primary-green: "#166534"
  error-red: "#D64545"
  background-neutral: "#F7F7F5"
  surface-light: "#E9EEF3"
  text-base: "#0E0E0E"
  text-muted: "#6B7280"
  border-subtle: "rgba(0,0,0,0.06)"
  accent-blue: "#4A90E2"
typography:
  display-xl:
    fontFamily: "Inter"
    fontSize: "72px"
    fontWeight: 500
    lineHeight: "1.05"
  heading-lg:
    fontFamily: "Inter"
    fontSize: "48px"
    fontWeight: 500
    lineHeight: "1.1"
  body-lg:
    fontFamily: "Inter"
    fontSize: "20px"
    fontWeight: 400
    lineHeight: "1.5"
  body-base:
    fontFamily: "Inter"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: "1.6"
  label-sm:
    fontFamily: "Inter"
    fontSize: "14px"
    fontWeight: 600
    lineHeight: "1.2"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "40px"
  section: "96px"
rounded:
  small: "6px"
  medium: "10px"
  large: "14px"
  extra-large: "18px"
  full: "999px"
components:
  button-primary:
    bg: "#166534"
    text: "#FFFFFF"
    rounded: "10px"
  status-pill:
    padding: "4px 10px"
    rounded: "6px"
    fontSize: "12px"
  data-table:
    border: "1px solid rgba(0,0,0,0.05)"
    header-bg: "#F9FAFB"
  alert-card:
    bg: "rgba(214, 69, 69, 0.05)"
    borderLeft: "4px solid #D64545"
motion:
  mismatch-shake: "0.5s cubic-bezier(.36,.07,.19,.97)"
  dash-flow: "dash 20s linear infinite"
---

## Overview
This design system is engineered for industrial environments where decision-making relies on spotting discrepancies. It uses a high-contrast palette of forest greens for success and urgent reds for anomalies, set against a neutral, fatigue-reducing off-white background.

## Colors
- Core colors use high-density pigments to ensure readability on factory-floor tablets.
- Red (#D64545) is reserved exclusively for mismatches, errors, and loss indicators.
- Green (#166534) signifies verified data and successful reconciliation.

## Typography
- The system uses Inter with tight tracking (-0.01em) to improve professional aesthetics.
- Heavy use of tabular figures for numerical data to ensure column alignment in reports.

## Spacing
- Utilizes a standard 8px grid system.
- Large section spacing (96px+) is used to prevent cognitive overload in complex data environments.

## Layout
- Standard container-width constraints of 1280px.
- Content is structured in a clear 'Top-to-Bottom' hierarchy, starting with high-level summaries and ending in granular data tables.

## Elevation & Depth
- Low-elevation shadows (0 10px 30px rgba(0,0,0,0.06)) provide depth without adding visual clutter.
- Border-based depth (1px solid) is preferred over heavy drop shadows.

## Shapes
- Precision corners (10px to 14px radius) for standard UI containers.
- Sharper 6px corners for small utility components like tags and badges.

## Components
- Navigation: Minimalist bar with high-contrast text and a primary action button.
- Dashboard Cards: White surfaces with subtle border-strokes to contain dense information.
- Data Tables: Alternating states with explicit 'Alert' rows that feature horizontal shaking motion on hover.
- Process Connectors: Dashed lines with CSS-driven dash-offset animations to show directional flow.

## Motion
- Use 'shake' animations only for critical data errors.
- Subtle 'pulse' indicators for live tracking status.
- Smooth 300ms transitions for hover states and card lifts.

## Do's and Don'ts
- DO use high-contrast text for all numerical data.
- DO highlight variance in Red as soon as a threshold is crossed.
- DON'T use vibrant colors for decorative elements; keep the focus on the data.
- DON'T use rounded corners above 20px, as it reduces the industrial feel.

## Accessibility
- Minimum contrast ratio of 4.5:1 for all text elements.
- Status indicators must use both color (red/green) and icons (warning/check) to assist color-blind users.