{
  description = "A YouTube Music Terminal User Interface";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils, ... }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};

        # Package up the local python environment
        pythonEnv = pkgs.python3.withPackages (ps: [
          ps.textual
          ps.ytmusicapi
          # Note: if python-mpv isn't in nixpkgs, nix will build it via pip
          (ps.toPythonModule pkgs.python3Packages.mpv)
        ]);
      in
      {
        packages.default = pkgs.stdenv.mkDerivation {
          pname = "ytmusic-tui";
          version = "1.0.0";
          src = ./.;

          # Runtime system dependencies that MUST be present for the binary to work
          buildInputs = [ pythonEnv pkgs.mpv pkgs.makeWrapper ];

          installPhase = ''
            mkdir -p $out/bin
            cp main.py $out/bin/ytmusic-tui-main
            cp player_manager.py $out/bin/
            cp browser.json $out/bin/ || true

            # Wrap the executable so it can always find the correct python and system libmpv
            makeWrapper ${pythonEnv}/bin/python3 $out/bin/ytmusic-tui \
              --add-flags "$out/bin/ytmusic-tui-main" \
              --prefix LD_LIBRARY_PATH : "${pkgs.mpv}/lib"
          '';
        };
      }
    );
}
