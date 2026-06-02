#!/usr/bin/env node
import React, {useEffect, useMemo, useState} from 'react';
import {Box, Text, render, useApp} from 'ink';
import {
	Alert,
	Badge,
	ConfirmInput,
	PasswordInput,
	Select,
	Spinner,
	StatusMessage,
	TextInput,
	ThemeProvider,
} from '@inkjs/ui';
import {fetchStatus, setOverride, setPumpState, type PumpStatus, type SshConfig} from './ssh.js';
import {customTheme} from './theme.js';

type ActionValue = 'pump-on' | 'pump-off' | 'override-clear' | 'refresh' | 'exit';
type Mode = 'connect' | 'dashboard' | 'confirm' | 'busy';

const DEFAULT_HOST = process.env.WILO_PI_HOST ?? 'wilopi.local';
const DEFAULT_USER = process.env.WILO_PI_USER ?? 'wilopi';
const DEFAULT_PORT = Number(process.env.WILO_PI_PORT ?? '22');
const DEFAULT_PASSWORD = process.env.WILO_PI_PASSWORD ?? '';

const number = (value: number | null | undefined, suffix = '', digits = 1): string => {
	if (value === null || value === undefined || Number.isNaN(value)) {
		return 'n/a';
	}

	return `${value.toFixed(digits)}${suffix}`;
};

const connectionSummary = (config: SshConfig): string =>
	`${config.username}@${config.host}:${config.port}`;

const App = () => {
	const {exit} = useApp();
	const [config, setConfig] = useState<SshConfig>({
		host: DEFAULT_HOST,
		password: DEFAULT_PASSWORD,
		port: DEFAULT_PORT,
		username: DEFAULT_USER,
	});
	const [mode, setMode] = useState<Mode>('connect');
	const [connectionStep, setConnectionStep] = useState<'host' | 'username' | 'password'>(
		DEFAULT_PASSWORD ? 'host' : 'host',
	);
	const [status, setStatus] = useState<PumpStatus | null>(null);
	const [selectedAction, setSelectedAction] = useState<ActionValue | null>(null);
	const [flashMessage, setFlashMessage] = useState<{variant: 'success' | 'error' | 'warning' | 'info'; text: string} | null>(null);
	const [busyLabel, setBusyLabel] = useState('Connecting to Pi');

	const statusVariant = useMemo(() => {
		if (!status) {
			return 'warning';
		}

		if (status.decision?.state?.startsWith('OFF_')) {
			return 'warning';
		}

		if (status.pump_relay_on) {
			return 'success';
		}

		return 'info';
	}, [status]);

	const refresh = async () => {
		const next = await fetchStatus(config);
		setStatus(next);
	};

	useEffect(() => {
		if (mode !== 'dashboard') {
			return;
		}

		void refresh();
		const timer = setInterval(() => {
			void refresh().catch(error => {
				setFlashMessage({variant: 'error', text: error instanceof Error ? error.message : String(error)});
			});
		}, 3000);

		return () => {
			clearInterval(timer);
		};
	}, [mode, config]);

	const connect = async () => {
		setBusyLabel(`Connecting to ${connectionSummary(config)}`);
		setMode('busy');
		try {
			await refresh();
			setMode('dashboard');
			setFlashMessage({variant: 'success', text: `Connected to ${connectionSummary(config)}`});
		} catch (error) {
			setMode('connect');
			setFlashMessage({
				variant: 'error',
				text: error instanceof Error ? error.message : String(error),
			});
		}
	};

	const runAction = async (action: ActionValue) => {
		if (action === 'refresh') {
			setBusyLabel('Refreshing Pi status');
			setMode('busy');
			try {
				await refresh();
				setMode('dashboard');
			} catch (error) {
				setMode('dashboard');
				setFlashMessage({variant: 'error', text: error instanceof Error ? error.message : String(error)});
			}
			return;
		}

		if (action === 'exit') {
			exit();
			return;
		}

		setSelectedAction(action);
		setMode('confirm');
	};

	const confirmAction = async () => {
		if (!selectedAction) {
			setMode('dashboard');
			return;
		}

		const labels: Record<ActionValue, string> = {
			'pump-on': 'Turning the pump relay ON',
			'pump-off': 'Turning the pump relay OFF',
			'override-clear': 'Clearing manual override',
			'refresh': 'Refreshing Pi status',
			'exit': 'Exiting',
		};

		setBusyLabel(labels[selectedAction]);
		setMode('busy');
		try {
			if (selectedAction === 'pump-on') {
				await setPumpState(config, 'on');
				setFlashMessage({variant: 'success', text: 'Pump relay forced ON from the Pi bridge'});
			} else if (selectedAction === 'pump-off') {
				await setPumpState(config, 'off');
				setFlashMessage({variant: 'warning', text: 'Pump relay forced OFF from the Pi bridge'});
			} else if (selectedAction === 'override-clear') {
				await setOverride(config, 'clear');
				setFlashMessage({variant: 'info', text: 'Manual override cleared on the Pi'});
			}

			await refresh();
		} catch (error) {
			setFlashMessage({variant: 'error', text: error instanceof Error ? error.message : String(error)});
		} finally {
			setSelectedAction(null);
			setMode('dashboard');
		}
	};

	if (mode === 'busy') {
		return (
			<ThemeProvider theme={customTheme}>
				<Box flexDirection="column" padding={1}>
					<Spinner label={busyLabel} />
				</Box>
			</ThemeProvider>
		);
	}

	if (mode === 'connect') {
		return (
			<ThemeProvider theme={customTheme}>
				<Box flexDirection="column" padding={1} gap={1}>
					<Text bold color="cyan">Wilo Pump TUI</Text>
					<Text>SSH into the Pi and send overrides through the running pump controller.</Text>
					{flashMessage ? <Alert variant={flashMessage.variant}>{flashMessage.text}</Alert> : null}
					<StatusMessage variant="info">
						Connection target: {connectionSummary(config)}
					</StatusMessage>

					{connectionStep === 'host' ? (
						<>
							<Text>Pi host</Text>
							<TextInput
								defaultValue={config.host}
								placeholder="wilopi.local"
								onSubmit={value => {
									setConfig(previous => ({...previous, host: value || previous.host}));
									setConnectionStep('username');
								}}
							/>
						</>
					) : null}

					{connectionStep === 'username' ? (
						<>
							<Text>SSH username</Text>
							<TextInput
								defaultValue={config.username}
								placeholder="wilopi"
								onSubmit={value => {
									setConfig(previous => ({...previous, username: value || previous.username}));
									setConnectionStep('password');
								}}
							/>
						</>
					) : null}

					{connectionStep === 'password' ? (
						<>
							<Text>SSH password</Text>
							<PasswordInput
								placeholder="Enter Pi password"
								onSubmit={value => {
									setConfig(previous => ({...previous, password: value || previous.password}));
									void connect();
								}}
							/>
						</>
					) : null}
				</Box>
			</ThemeProvider>
		);
	}

	if (mode === 'confirm') {
		const labelByAction: Record<ActionValue, string> = {
			'pump-on': 'Force the pump relay ON directly on the Pi?',
			'pump-off': 'Force the pump relay OFF directly on the Pi?',
			'override-clear': 'Clear any active manual override?',
			'refresh': 'Refresh status?',
			'exit': 'Exit the TUI?',
		};

		return (
			<ThemeProvider theme={customTheme}>
				<Box flexDirection="column" padding={1} gap={1}>
					<Alert variant={selectedAction === 'pump-on' ? 'warning' : 'info'}>
						{selectedAction ? labelByAction[selectedAction] : 'Confirm action'}
					</Alert>
					<ConfirmInput
						onConfirm={() => {
							void confirmAction();
						}}
						onCancel={() => {
							setSelectedAction(null);
							setMode('dashboard');
						}}
					/>
				</Box>
			</ThemeProvider>
		);
	}

	return (
		<ThemeProvider theme={customTheme}>
			<Box flexDirection="column" padding={1} gap={1}>
				<Box justifyContent="space-between">
					<Text bold color="cyan">Wilo Pump Console</Text>
					<Text>{connectionSummary(config)}</Text>
				</Box>

				{flashMessage ? <Alert variant={flashMessage.variant}>{flashMessage.text}</Alert> : null}

				<Box gap={3}>
					<Box flexDirection="column" width={64} gap={1}>
						<StatusMessage variant={statusVariant}>
							{status?.pump_relay_on ? 'Pump relay is currently ON' : 'Pump relay is currently OFF'}
						</StatusMessage>

						<Box flexDirection="column">
							<Text><Text bold>Upper tank:</Text> {number(status?.upper_pct ?? null, '%')}</Text>
							<Text><Text bold>Pressure:</Text> {number(status?.pressure_kpa ?? null, ' kPa', 2)}</Text>
							<Text><Text bold>Current:</Text> {number(status?.current_amps ?? null, ' A', 2)}</Text>
							<Text><Text bold>Voltage:</Text> {number(status?.voltage_ac ?? null, ' V', 1)}</Text>
							<Text><Text bold>LoRa:</Text> pkt {status?.lora_pkt ?? 'n/a'} / age {number(status?.lora_age_s ?? null, ' s', 1)}</Text>
							<Text><Text bold>Decision:</Text> {status?.decision?.state ?? 'n/a'}</Text>
							<Text><Text bold>Reason:</Text> {status?.decision?.reason ?? 'n/a'}</Text>
						</Box>

						<Box gap={1}>
							<Badge color={status?.override ? 'yellow' : 'blue'}>override {status?.override ?? 'none'}</Badge>
							<Badge color={status?.sensor_status === 'ok' ? 'green' : 'yellow'}>sensor {status?.sensor_status ?? 'unknown'}</Badge>
							<Badge color={status?.connected ? 'green' : 'red'}>{status?.controller_mode ?? 'unknown'}</Badge>
						</Box>
					</Box>

					<Box flexDirection="column" width={42} gap={1}>
						<Text bold>Controls</Text>
						<Select
							options={[
								{label: 'Turn pump ON now', value: 'pump-on'},
								{label: 'Turn pump OFF now', value: 'pump-off'},
								{label: 'Clear manual override', value: 'override-clear'},
								{label: 'Refresh now', value: 'refresh'},
								{label: 'Exit', value: 'exit'},
							]}
							onChange={value => {
								void runAction(value as ActionValue);
							}}
						/>
					</Box>
				</Box>
			</Box>
		</ThemeProvider>
	);
};

render(<App />);
