# cloudlab-bypass-356

## Set-Up Instructions
Step 1: Install dependencies

Run this command to install all prerequisites:

sudo apt update

sudo apt install -y autotools-dev protobuf-compiler libprotobuf-dev dh-autoreconf \
iptables pkg-config dnsmasq-base apache2-bin apache2-dev debhelper \
libssl-dev ssl-cert libxcb-present-dev libcairo2-dev libpango1.0-dev git build-essential

=========================
Step 2: Clone the Mahimahi repo
git clone https://github.com/ravinet/mahimahi.git
cd mahimahi

=========================
Step 3: Patch the C++ flags

Mahimahi’s configure.ac has flags -Wall -Wextra that break with newer GCC.
Edit line 15 of configure.ac to remove them:

nano configure.ac

Look for something like:
PICKY CXXFLAGS="-Wall -Wextra -pedantic -Weffc++"

Change it to:
PICKY CXXFLAGS="-pedantic -Weffc++"

Save and exit (Ctrl+O, Enter, Ctrl+X in nano).

=========================
Step 4: Build and install
Run the usual autotools commands:
./autogen.sh
./configure
make
sudo make install

After this, binaries like `mm-delay` and `mm-link` should be in your path. You can check with:

which mm-delay
which mm-link

=========================
Step 5: Create a link trace file

If you want a 12 Mbit/s link:

echo 1 > 12mbps


1 line = 12 Mbit/s

For 6 Mbit/s, put 2 in the file.

For 24 Mbit/s, put 1 twice.

## Running the Code

### Running Without Emulator (Like Assignment 3)
Added files from previous assignment:
`test_file.txt`
`generate_bogus_text.py`

python3 generate_bogus_text.py 1000000 >test_file.txt 
python3 transport.py --ip localhost --port 7000 receiver
python3 transport.py --ip localhost --port 7000 --sendfile test_file.txt sender

### Running With Emulator (Change `localhost`)
Find out the host `ip address` by running `ip addr` (check for anything that is not `lo` - that's localhost).

Or, you can run `hostname -I` and get the first IP address that is not `127.0.0.1` - that's loopback or localhost.

// For the receiver:
// This should be done outside of the mahimahi shell
`python3 transport.py --ip 0.0.0.0 --port 7000 receiver`

// For the sender:
To start the mahimahi shell, run
```
mm-delay 10 mm-link --uplink-queue=droptail \
--uplink-queue-args=bytes=30000 --downlink-queue=infinite 12mbps 12mbps
```
// This should be done inside the mahimahi shell
`python3 transport.py --ip 128.105.145.101 --port 7000 --sendfile test_file.txt sender`

// Replace `<128.105.145.101>` with the actual host IP obtained above.
