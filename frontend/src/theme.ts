import {
  Badge,
  Button,
  Card,
  createTheme,
  Drawer,
  Modal,
  Paper,
  Progress,
  SegmentedControl,
  Table,
  Tooltip,
  type MantineColorsTuple,
} from '@mantine/core'

const ink: MantineColorsTuple = [
  '#f4f2ee',
  '#e6e3dc',
  '#cbc6bb',
  '#ada697',
  '#8f8878',
  '#736c5e',
  '#5a544a',
  '#433f37',
  '#2d2a25',
  '#1a1916',
]

const thread: MantineColorsTuple = [
  '#fff1ec',
  '#ffe0d5',
  '#fbbfa8',
  '#f69b78',
  '#f17c4f',
  '#ee6835',
  '#ec5d27',
  '#d24c1a',
  '#bb4215',
  '#a3360e',
]

const gray: MantineColorsTuple = [
  '#faf9f6',
  '#f4f2ed',
  '#ebe8e1',
  '#dfdbd2',
  '#cdc8bd',
  '#aaa498',
  '#848075',
  '#615d54',
  '#48453e',
  '#1a1916',
]

const dark: MantineColorsTuple = [
  '#ece9e2',
  '#c9c5bc',
  '#a29e95',
  '#7d7970',
  '#57544d',
  '#3a3833',
  '#2b2925',
  '#1e1d1a',
  '#161512',
  '#0f0e0c',
]

export const theme = createTheme({
  primaryColor: 'ink',
  primaryShade: { light: 9, dark: 1 },
  autoContrast: true,
  colors: { ink, thread, gray, dark },
  black: '#1a1916',
  white: '#fffefb',
  fontFamily: '"IBM Plex Sans", ui-sans-serif, system-ui, "Segoe UI", sans-serif',
  fontFamilyMonospace: '"IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, monospace',
  headings: {
    fontFamily: '"IBM Plex Sans", ui-sans-serif, system-ui, sans-serif',
    fontWeight: '600',
    sizes: {
      h1: { fontSize: '2.375rem', lineHeight: '1.1', fontWeight: '400' },
      h2: { fontSize: '1.5rem', lineHeight: '1.25' },
      h3: { fontSize: '1.125rem', lineHeight: '1.35' },
      h4: { fontSize: '1rem', lineHeight: '1.4' },
    },
  },
  defaultRadius: 'xs',
  radius: { xs: '2px', sm: '3px', md: '4px', lg: '6px', xl: '10px' },
  cursorType: 'pointer',
  focusRing: 'auto',
  components: {
    Card: Card.extend({ defaultProps: { withBorder: true, radius: 'sm', padding: 'lg', shadow: 'none' } }),
    Paper: Paper.extend({ defaultProps: { radius: 'sm' } }),
    Button: Button.extend({ defaultProps: { radius: 'xs' } }),
    Badge: Badge.extend({ defaultProps: { radius: 'xs', tt: 'none', fw: 500, variant: 'outline', color: 'gray.7' } }),
    Tooltip: Tooltip.extend({ defaultProps: { withArrow: false, openDelay: 250, radius: 'xs', color: 'ink.9' } }),
    Drawer: Drawer.extend({ defaultProps: { position: 'right', size: 'lg', padding: 'xl', radius: 0 } }),
    Modal: Modal.extend({ defaultProps: { radius: 'sm', centered: true } }),
    Table: Table.extend({ defaultProps: { verticalSpacing: 'sm', horizontalSpacing: 'md', highlightOnHover: true } }),
    SegmentedControl: SegmentedControl.extend({ defaultProps: { radius: 'xs' } }),
    Progress: Progress.extend({ defaultProps: { radius: 0, size: 4 } }),
  },
})
