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

        pythonEnv = pkgs.python3.withPackages (ps: [
          ps.textual
          ps.ytmusicapi
          ps.httpx
          ps.pillow
          ps.textual-image
          (ps.toPythonModule pkgs.python3Packages.mpv)
        ]);
      in
      {
        packages.default = pkgs.stdenv.mkDerivation {
          pname = "ytmusic-tui";
          version = "1.0.0";
          src = ./.;

          buildInputs = [ pythonEnv pkgs.mpv pkgs.yt-dlp pkgs.makeWrapper ];

          installPhase = ''
            mkdir -p $out/bin
            cp main.py $out/bin/ytmusic-tui-main
            cp player_manager.py $out/bin/
            cp style.tcss $out/bin/  
            cp browser.json $out/bin/ || true

            makeWrapper ${pythonEnv}/bin/python3 $out/bin/ytmusic-tui \
              --add-flags "$out/bin/ytmusic-tui-main" \
              --prefix LD_LIBRARY_PATH : "${pkgs.mpv}/lib" \
              --prefix PATH : "${pkgs.yt-dlp}/bin"
          '';
        };
      }
    );
}
