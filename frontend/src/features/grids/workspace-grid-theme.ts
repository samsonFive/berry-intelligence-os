import { themeQuartz } from 'ag-grid-community';

/** Shared read-only grid presentation follows the established Workspaces sheet. */
export const workspaceGridTheme = themeQuartz.withParams({
  fontFamily: 'var(--berry-font-ui)', fontSize: 12,
  backgroundColor: 'var(--berry-surface)', foregroundColor: 'var(--berry-ink)',
  headerBackgroundColor: '#254b36', headerTextColor: '#ffffff',
  oddRowBackgroundColor: '#f0f5ef', rowHoverColor: '#e5efe2',
  accentColor: 'var(--berry-forest)', borderColor: 'var(--berry-line-strong)',
  rowBorder: true, columnBorder: true, headerHeight: 34, spacing: 3,
  wrapperBorderRadius: 0,
});
